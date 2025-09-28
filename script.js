// --- Variáveis globais ---
let map = null;
let youMarker = null;
let themMarker = null;
let youPos = null;
let themPos = null;
let connectionLine = null;

// --- Inicialização do mapa ---
function initMap() {
    map = L.map('map').setView([-23.55052, -46.6333], 10);
    
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '© OpenStreetMap contributors'
    }).addTo(map);
    
    // Ícones personalizados românticos
    const heartIcon = L.divIcon({
        html: '<div style="font-size: 24px; text-shadow: 2px 2px 4px rgba(0,0,0,0.3);">❤️</div>',
        iconSize: [30, 30],
        className: 'heart-icon'
    });
    
    const partnerIcon = L.divIcon({
        html: '<div style="font-size: 24px; text-shadow: 2px 2px 4px rgba(0,0,0,0.3);">💕</div>',
        iconSize: [30, 30],
        className: 'partner-icon'
    });
    
    // Criar marcadores iniciais (invisíveis)
    youMarker = L.marker([0, 0], { icon: heartIcon }).addTo(map);
    themMarker = L.marker([0, 0], { icon: partnerIcon }).addTo(map);
    
    youMarker.setOpacity(0);
    themMarker.setOpacity(0);
}

// --- Função para calcular distância ---
function calculateDistance(lat1, lng1, lat2, lng2) {
    const R = 6371000; // Raio da Terra em metros
    const dLat = (lat2 - lat1) * Math.PI / 180;
    const dLng = (lng2 - lng1) * Math.PI / 180;
    const a = Math.sin(dLat/2) * Math.sin(dLat/2) +
              Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) *
              Math.sin(dLng/2) * Math.sin(dLng/2);
    const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a));
    const distance = R * c;
    
    if (distance < 1000) {
        return Math.round(distance) + ' m';
    } else {
        return (distance / 1000).toFixed(2) + ' km';
    }
}

// --- Função para formatar tempo ---
function formatTime(timestamp) {
    const date = new Date(timestamp);
    return date.toLocaleTimeString('pt-BR');
}

// --- Função para atualizar marcadores ---
function updateMarkers() {
    if (!map) return;
    
    let bounds = null;
    
    if (youPos) {
        youMarker.setLatLng([youPos.lat, youPos.lng]);
        youMarker.setOpacity(1);
        youMarker.bindPopup(`💖 Você está aqui!<br><small>Atualizado: ${formatTime(youPos.t)}</small>`);
        document.getElementById('youTime').textContent = formatTime(youPos.t);
        
        if (!bounds) bounds = L.latLngBounds([youPos.lat, youPos.lng], [youPos.lat, youPos.lng]);
        else bounds.extend([youPos.lat, youPos.lng]);
    }
    
    if (themPos) {
        themMarker.setLatLng([themPos.lat, themPos.lng]);
        themMarker.setOpacity(1);
        themMarker.bindPopup(`💕 Sua parceira está aqui!<br><small>Atualizado: ${formatTime(themPos.t)}</small>`);
        document.getElementById('themTime').textContent = formatTime(themPos.t);
        
        if (!bounds) bounds = L.latLngBounds([themPos.lat, themPos.lng], [themPos.lat, themPos.lng]);
        else bounds.extend([themPos.lat, themPos.lng]);
    }
    
    // Calcular e mostrar distância
    if (youPos && themPos) {
        const distance = calculateDistance(youPos.lat, youPos.lng, themPos.lat, themPos.lng);
        document.getElementById('distance').textContent = distance;
        
        // Mostrar mensagem romântica baseada na distância
        showLoveMessage(distance);
        
        // Linha conectando os dois pontos
        if (connectionLine) {
            map.removeLayer(connectionLine);
        }
        
        connectionLine = L.polyline([
            [youPos.lat, youPos.lng],
            [themPos.lat, themPos.lng]
        ], {
            color: '#ff6b98',
            weight: 3,
            opacity: 0.7,
            dashArray: '10, 10'
        }).addTo(map);
        
        // Adicionar coração no meio da linha
        const midLat = (youPos.lat + themPos.lat) / 2;
        const midLng = (youPos.lng + themPos.lng) / 2;
        
        const midIcon = L.divIcon({
            html: '<div style="font-size: 20px; animation: pulse 2s infinite;">💖</div>',
            iconSize: [25, 25],
            className: 'mid-heart'
        });
        
        L.marker([midLat, midLng], { icon: midIcon })
            .addTo(map)
            .bindPopup(`💖 Distância: ${distance}`);
    }
    
    // Ajustar zoom para mostrar ambos os pontos
    if (bounds) {
        map.fitBounds(bounds, { padding: [50, 50] });
    }
}

// --- Função para mostrar mensagens românticas ---
function showLoveMessage(distance) {
    const loveMessageEl = document.getElementById('loveMessage');
    const messages = [
        "💌 \"A distância não é nada quando alguém significa tudo para você.\"",
        "💕 \"Cada quilômetro que nos separa é uma razão a mais para nos amarmos.\"",
        "❤️ \"O amor verdadeiro não conhece distâncias.\"",
        "💖 \"Mesmo longe, meu coração está sempre perto do seu.\"",
        "🌟 \"A distância é apenas um número, o amor é infinito.\"",
        "💝 \"Cada segundo longe de você é uma eternidade.\"",
        "🌹 \"O amor conecta corações independente da distância.\""
    ];
    
    if (loveMessageEl) {
        const randomMessage = messages[Math.floor(Math.random() * messages.length)];
        loveMessageEl.innerHTML = `<small>${randomMessage}</small>`;
        loveMessageEl.style.display = 'block';
        
        // Adicionar efeito de fade in
        loveMessageEl.style.opacity = '0';
        setTimeout(() => {
            loveMessageEl.style.opacity = '1';
        }, 100);
    }
}

// --- Geolocalização em tempo real (watch) ---
if('geolocation' in navigator){
    navigator.geolocation.watchPosition(pos => {
        youPos = { lat: pos.coords.latitude, lng: pos.coords.longitude, t: Date.now() };
        updateMarkers();
        if(window.firebaseConnected) sendToFirebase();
        
        // Mostrar status de conexão
        updateConnectionStatus('Localização atualizada ❤️');
    }, err => {
        console.warn('geolocation error', err);
        alert('Erro ao obter sua localização. Libere permissão e tente novamente.');
        updateConnectionStatus('Erro na localização ⚠️');
    }, { enableHighAccuracy: true, maximumAge: 5000, timeout: 10000 });
} else {
    alert('Geolocalização não suportada neste navegador.');
}

// --- Função para atualizar status de conexão ---
function updateConnectionStatus(message) {
    const statusElement = document.getElementById('connectionStatus');
    if (statusElement) {
        statusElement.textContent = message;
        statusElement.style.opacity = '1';
        setTimeout(() => {
            statusElement.style.opacity = '0.7';
        }, 2000);
    }
}

// --- UI Handlers ---
const modeSelect = document.getElementById('mode');
const shareControls = document.getElementById('shareControls');
const firebaseControls = document.getElementById('firebaseControls');

modeSelect.addEventListener('change', ()=>{
    shareControls.style.display = modeSelect.value === 'sharelink' ? 'block' : 'none';
    firebaseControls.style.display = modeSelect.value === 'firebase' ? 'block' : 'none';
});

document.getElementById('generateLink').addEventListener('click', ()=>{
    if(!youPos){ alert('Aguardando sua posição...'); return; }
    const url = new URL(location.href);
    url.hash = `you=${youPos.lat},${youPos.lng},${youPos.t}`;
    navigator.clipboard.writeText(url.toString()).then(()=>{
        alert('Link copiado! Envie para ela. 💕');
        updateConnectionStatus('Link compartilhado! 💌');
    });
});

function parseHash(){
    const h = location.hash.slice(1);
    if(!h) return;
    if(h.startsWith('you=')){
        const [lat,lng,t] = h.replace('you=','').split(',').map(Number);
        if(!isNaN(lat) && !isNaN(lng)){
            themPos = {lat, lng, t: t || Date.now()};
            updateMarkers();
            updateConnectionStatus('Localização da parceira recebida! 💕');
        }
    }
}
parseHash();

window.addEventListener('hashchange', ()=>{ parseHash(); });

document.getElementById('setPartner').addEventListener('click', ()=>{
    const lat = parseFloat(document.getElementById('partnerLat').value);
    const lng = parseFloat(document.getElementById('partnerLng').value);
    if(isNaN(lat) || isNaN(lng)) { alert('Coordenadas inválidas'); return; }
    themPos = {lat, lng, t: Date.now()};
    updateMarkers();
    updateConnectionStatus('Localização manual definida! 📍');
});

// --- Firebase ---
let database = null;
let room = null;

document.getElementById('connectFirebase').addEventListener('click', ()=>{
    const raw = document.getElementById('firebaseConfig').value.trim();
    const roomId = document.getElementById('roomId').value.trim();
    if(!roomId) { alert('Defina um ID de sala.'); return; }
    let cfg = null;
    if(raw){
        try{ cfg = JSON.parse(raw); } catch(e){ alert('Config Firebase inválida'); return; }
    }
    if(!cfg){ alert('Cole a configuração do Firebase.'); return; }

    try{
        if(window.firebase && window.firebase.apps && window.firebase.apps.length === 0){
            window.firebase.initializeApp(cfg);
        }
        database = firebase.database();
        room = roomId;
        window.firebaseConnected = true;

        const ref = database.ref('rooms/' + room + '/them');
        ref.on('value', snap => {
            const v = snap.val();
            if(v && v.lat && v.lng){
                themPos = { lat: v.lat, lng: v.lng, t: v.t || Date.now() };
                updateMarkers();
                updateConnectionStatus('Conectado em tempo real! 💖');
            }
        });
        
        alert('Conectado ao Firebase! Use o mesmo roomId e config no outro aparelho. 💕');
        updateConnectionStatus('Firebase conectado! 🔥');
    } catch(e){
        console.error(e); 
        alert('Erro ao conectar ao Firebase. Veja console.');
        updateConnectionStatus('Erro no Firebase ⚠️');
    }
});

function sendToFirebase(){
    if(!database || !room || !youPos) return;
    const ref = database.ref('rooms/' + room + '/you');
    ref.set({ lat: youPos.lat, lng: youPos.lng, t: youPos.t });
}

// --- Inicializar quando a página carregar ---
document.addEventListener('DOMContentLoaded', () => {
    initMap();
    updateConnectionStatus('Mapa carregado! Aguardando localização... 💖');
});

console.log('Mapa da Distância pronto. Permita geolocalização e configure o Firebase para tempo real. 💕');