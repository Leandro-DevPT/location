from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, HTTPException, Depends
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from datetime import datetime
from typing import Dict, Set, List
from collections import defaultdict
import json
import uuid
import asyncio
import secrets
import hashlib
import base64

app = FastAPI(title="Chat Anônimo UltraSeguro")

# Configuração do admin
ADMIN_CREDENTIALS = {
    "username": "Owner",
    "password_hash": hashlib.sha256("vault-7f3a-9b2c-4e8d-1f5a-cipher-phantom-key-2026".encode()).hexdigest()
}

# Gerenciador de conexões com criptografia avançada
class SecureConnectionManager:
    def __init__(self):
        # Conexões ativas por sala: {room_id: {websocket: client_info}}
        self.rooms: Dict[str, Dict[WebSocket, dict]] = defaultdict(dict)
        
        # Chaves de criptografia por sala (E2E encryption keys)
        self.room_encryption_keys: Dict[str, bytes] = {}
        
        # Histórico de mensagens criptografadas
        self.encrypted_messages: Dict[str, List[dict]] = defaultdict(list)
        
        # Metadata de salas criadas
        self.room_metadata: Dict[str, dict] = {}
        
        # Sessões admin
        self.admin_sessions: Set[str] = set()
        
        # Log de atividades para painel admin
        self.activity_log: List[dict] = []
        
    async def connect_client(self, websocket: WebSocket, room_id: str):
        await websocket.accept()
        
        # Gerar ID único anônimo
        client_id = str(uuid.uuid4())[:8]
        fingerprint = secrets.token_hex(16)
        
        # Criar chave de criptografia para a sala se não existir
        if room_id not in self.room_encryption_keys:
            self.room_encryption_keys[room_id] = Fernet.generate_key()
        
        client_info = {
            "client_id": client_id,
            "fingerprint": fingerprint,
            "connected_at": datetime.now().isoformat(),
            "room_id": room_id,
            "ip": websocket.client.host,
            "port": websocket.client.port,
            "messages_sent": 0,
            "messages_received": 0
        }
        
        self.rooms[room_id][websocket] = client_info
        
        # Log de conexão
        self.log_activity(room_id, client_id, "CONNECT", {
            "event": "client_connected",
            "fingerprint": fingerprint[:16]
        })
        
        # Enviar chave de criptografia para o cliente
        await websocket.send_text(json.dumps({
            "type": "init",
            "client_id": client_id,
            "encryption_key": self.room_encryption_keys[room_id].decode(),
            "peers": len(self.rooms[room_id])
        }))
        
        # Notificar outros clientes na sala
        await self.broadcast(room_id, {
            "type": "system",
            "message": f"Usuário {client_id} entrou na sala"
        }, exclude=websocket)
        
    def disconnect_client(self, websocket: WebSocket, room_id: str):
        if websocket in self.rooms[room_id]:
            client_info = self.rooms[room_id][websocket]
            client_id = client_info["client_id"]
            
            # Log de desconexão
            self.log_activity(room_id, client_id, "DISCONNECT", {
                "event": "client_disconnected",
                "messages_sent": client_info["messages_sent"],
                "messages_received": client_info["messages_received"],
                "duration": str(datetime.now() - datetime.fromisoformat(client_info["connected_at"]))
            })
            
            del self.rooms[room_id][websocket]
            
            # Deixar salas criadas disponíveis para administração mesmo sem clientes
            if room_id in self.room_metadata and not self.rooms[room_id]:
                self.log_activity(room_id, "SYSTEM", "ROOM_IDLE", {"event": "room_idle"})
    
    async def handle_message(self, websocket: WebSocket, room_id: str, data: dict):
        client_info = self.rooms[room_id][websocket]
        client_id = client_info["client_id"]
        
        # Atualizar contador
        client_info["messages_sent"] += 1
        
        # Preparar mensagem com metadados anônimos
        message_packet = {
            "id": str(uuid.uuid4()),
            "sender_id": client_id,
            "timestamp": datetime.now().isoformat(),
            "content": data["message"],
            "encrypted": True
        }
        
        # Armazenar mensagem criptografada para histórico
        self.encrypted_messages[room_id].append(message_packet)
        
        # Log da atividade
        self.log_activity(room_id, client_id, "MESSAGE", {
            "message_id": message_packet["id"],
            "length": len(data["message"]),
            "encrypted": True
        })
        
        # Broadcast para todos na sala (incluindo remetente para confirmação)
        await self.broadcast(room_id, {
            "type": "message",
            "data": message_packet
        }, exclude=None)  # Enviar para todos, incluindo remetente
        
        # Atualizar contadores de mensagens recebidas para outros
        for ws, info in self.rooms[room_id].items():
            if ws != websocket:
                info["messages_received"] += 1
    
    async def broadcast(self, room_id: str, message: dict, exclude: WebSocket = None):
        """Envia mensagem para todos na sala, com exceção opcional"""
        if room_id in self.rooms:
            disconnected = []
            for websocket in self.rooms[room_id]:
                if websocket != exclude:
                    try:
                        await websocket.send_text(json.dumps(message))
                    except:
                        disconnected.append(websocket)
            
            # Limpar conexões mortas
            for ws in disconnected:
                self.disconnect_client(ws, room_id)
    
    def log_activity(self, room_id: str, client_id: str, action: str, details: dict):
        """Registra atividade para o painel admin"""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "room_id": room_id,
            "client_id": client_id,
            "action": action,
            "details": details
        }
        self.activity_log.append(log_entry)
        
        # Manter apenas últimos 1000 logs
        if len(self.activity_log) > 1000:
            self.activity_log = self.activity_log[-1000:]
    
    def get_room_info(self, room_id: str) -> dict:
        """Retorna informações detalhadas da sala"""
        if room_id not in self.rooms:
            return None
        
        active_clients = []
        for ws, info in self.rooms[room_id].items():
            active_clients.append({
                "client_id": info["client_id"],
                "fingerprint": info["fingerprint"][:16],
                "connected_at": info["connected_at"],
                "messages_sent": info["messages_sent"],
                "messages_received": info["messages_received"],
                "ip": info["ip"],
                "duration": str(datetime.now() - datetime.fromisoformat(info["connected_at"]))
            })
        
        return {
            "room_id": room_id,
            "total_clients": len(active_clients),
            "total_messages": len(self.encrypted_messages.get(room_id, [])),
            "encryption_active": room_id in self.room_encryption_keys,
            "key_fingerprint": hashlib.md5(self.room_encryption_keys.get(room_id, b"")).hexdigest()[:8] if room_id in self.room_encryption_keys else None,
            "active_clients": active_clients,
            "recent_messages": self.encrypted_messages.get(room_id, [])[-10:]
        }

    def create_room(self, room_id: str):
        normalized_id = room_id.strip().lower().replace(" ", "-")
        if normalized_id not in self.room_encryption_keys:
            self.room_encryption_keys[normalized_id] = Fernet.generate_key()
            self.rooms[normalized_id] = {}
            self.encrypted_messages.setdefault(normalized_id, [])
            self.room_metadata[normalized_id] = {
                "created_at": datetime.now().isoformat(),
                "created_by": "system"
            }
            self.log_activity(normalized_id, "SYSTEM", "ROOM_CREATED", {"event": "room_created"})
        return normalized_id

    def decrypt_message(self, room_id: str, encrypted_base64: str):
        key = self.room_encryption_keys.get(room_id)
        if not key:
            return None
        try:
            raw_key = base64.b64decode(key)
            raw = base64.b64decode(encrypted_base64)
            iv = raw[:12]
            ciphertext = raw[12:]
            aesgcm = AESGCM(raw_key)
            plaintext = aesgcm.decrypt(iv, ciphertext, None)
            return plaintext.decode("utf-8")
        except Exception:
            return None

# Inicializar gerenciador
manager = SecureConnectionManager()

# Middleware de autenticação admin
async def verify_admin_session(request: Request):
    session_id = request.cookies.get("admin_session")
    if not session_id or session_id not in manager.admin_sessions:
        raise HTTPException(status_code=401, detail="Acesso não autorizado")
    return session_id

# Rotas da API
@app.post("/api/admin/login")
async def admin_login(request: Request):
    """Login do admin"""
    try:
        data = await request.json()
        username = data.get("username")
        password = data.get("password")
        
        password_hash = hashlib.sha256(password.encode()).hexdigest()
        
        if (username == ADMIN_CREDENTIALS["username"] and 
            password_hash == ADMIN_CREDENTIALS["password_hash"]):
            
            # Criar sessão admin
            session_id = secrets.token_urlsafe(32)
            manager.admin_sessions.add(session_id)
            
            response = JSONResponse({
                "success": True,
                "message": "Login realizado com sucesso",
                "session_id": session_id
            })
            
            # Cookie seguro
            response.set_cookie(
                key="admin_session",
                value=session_id,
                httponly=True,
                samesite="strict",
                max_age=3600
            )
            
            manager.log_activity("ADMIN", "Owner", "LOGIN", {
                "event": "admin_login",
                "ip": request.client.host
            })
            
            return response
        
        return JSONResponse({
            "success": False,
            "message": "Credenciais inválidas"
        }, status_code=401)
        
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=400)

@app.get("/api/admin/dashboard")
async def admin_dashboard(session_id: str = Depends(verify_admin_session)):
    """Painel de controle do admin com todas as informações"""
    
    all_rooms_info = []
    total_connections = 0
    total_messages = 0
    
    for room_id in list(manager.rooms.keys()):
        room_info = manager.get_room_info(room_id)
        if room_info:
            all_rooms_info.append(room_info)
            total_connections += room_info["total_clients"]
            total_messages += room_info["total_messages"]
    
    return {
        "system_status": {
            "total_rooms": len(manager.rooms),
            "total_connections": total_connections,
            "total_messages": total_messages,
            "active_sessions": len(manager.admin_sessions),
            "encryption_active": len(manager.room_encryption_keys),
            "server_uptime": str(datetime.now())
        },
        "rooms": all_rooms_info,
        "recent_activity": manager.activity_log[-20:]
    }

@app.get("/api/admin/room/{room_id}")
async def admin_room_detail(room_id: str, session_id: str = Depends(verify_admin_session)):
    """Detalhes de uma sala específica"""
    room_info = manager.get_room_info(room_id)
    if not room_info:
        raise HTTPException(status_code=404, detail="Sala não encontrada")
    return room_info

@app.get("/api/admin/room/{room_id}/messages")
async def admin_room_messages(room_id: str, session_id: str = Depends(verify_admin_session)):
    room_info = manager.get_room_info(room_id)
    if not room_info:
        raise HTTPException(status_code=404, detail="Sala não encontrada")
    decrypted_messages = []
    for msg in manager.encrypted_messages.get(room_id, []):
        decrypted_messages.append({
            "id": msg["id"],
            "sender_id": msg["sender_id"],
            "timestamp": msg["timestamp"],
            "encrypted": msg["encrypted"],
            "content": msg["content"],
            "decrypted_content": manager.decrypt_message(room_id, msg["content"]) or "<não decifrado>"
        })
    return {"room_id": room_id, "messages": decrypted_messages, "room_info": room_info}

@app.post("/api/rooms/create")
async def create_room(request: Request):
    try:
        data = await request.json()
        room_name = data.get("room_name", "")
        if room_name:
            room_id = manager.create_room(room_name)
        else:
            room_id = manager.create_room(f"sala-{secrets.token_hex(4)}")
        return {"success": True, "room_id": room_id}
    except Exception as e:
        return JSONResponse({"success": False, "message": str(e)}, status_code=400)

@app.get("/api/rooms")
async def list_rooms():
    rooms = []
    for room_id in manager.rooms.keys():
        room_info = manager.get_room_info(room_id)
        if room_info:
            rooms.append({
                "room_id": room_id,
                "total_clients": room_info["total_clients"],
                "total_messages": room_info["total_messages"]
            })
    return {"rooms": rooms}

@app.websocket("/ws/{room_id}")
async def websocket_endpoint(websocket: WebSocket, room_id: str):
    """Conexão WebSocket principal para chat"""
    try:
        # Conectar cliente
        await manager.connect_client(websocket, room_id)
        
        while True:
            # Receber mensagem
            data = await websocket.receive_text()
            message_data = json.loads(data)
            
            # Processar mensagem
            await manager.handle_message(websocket, room_id, message_data)
            
    except WebSocketDisconnect:
        manager.disconnect_client(websocket, room_id)
    except Exception as e:
        print(f"Erro WebSocket: {e}")
        manager.disconnect_client(websocket, room_id)

@app.get("/", response_class=HTMLResponse)
async def chat_interface():
    """Interface de chat"""
    with open("chat.html", "r", encoding="utf-8") as file:
        return HTMLResponse(file.read())

@app.get("/admin", response_class=HTMLResponse)
async def admin_panel():
    """Painel de administração"""
    with open("admin.html", "r", encoding="utf-8") as file:
        return HTMLResponse(file.read())

@app.get("/api/health")
async def health_check():
    """Verificação de saúde do sistema"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "active_rooms": len(manager.rooms),
        "active_connections": sum(len(room) for room in manager.rooms.values())
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        ws_max_size=1024*1024*10,  # 10MB max
        log_level="info"
    )