
#include <Arduino.h>
#include <WiFi.h>
#include <WebServer.h>

// Mettre 0 pour les premiers essais moteurs si le LiDAR perturbe le Wi-Fi.
#define ACTIVER_LIDAR 1
#if ACTIVER_LIDAR
#include "ld06.h"
#endif

// ------------------------------------------------------------
// RESEAU WIFI
// ------------------------------------------------------------
const char* WIFI_SSID = "RobotESP32";
const char* WIFI_PASSWORD = "12345678";
WebServer server(80);

// ------------------------------------------------------------
// MOTEURS : branchements testes et valides
// ------------------------------------------------------------
//              M1  M2  M3  M4
const uint8_t A[4] = {5, 19, 2, 16};
const uint8_t B[4] = {18, 21, 4, 17};

// Observations : M1/M4 inverses, M2/M3 dans le sens normal.
const int8_t AVANT[4] = {-1, +1, +1, -1};

// Configuration provisoire des positions physiques :
// M1 = avant gauche ; M2 = avant droite ; M3 = arriere gauche ; M4 = arriere droite.
// Les roues gauche reculent et les roues droite avancent pour tourner a gauche.
// Si le robot ne pivote pas correctement, verifier la POSITION des moteurs.
// Motifs exprimes en "sens avant de chaque roue" (+1/-1).
// INDEX : 0 AVANCER ; 1 RECULER ; 2 PIVOTER GAUCHE ; 3 PIVOTER DROITE ;
//         4 GLISSER GAUCHE ; 5 GLISSER DROITE.
const int8_t MOTIFS[6][4] = {
  {+1, +1, +1, +1}, // avancer
  {-1, -1, -1, -1}, // reculer
  {-1, +1, -1, +1}, // tourner gauche sur place
  {+1, -1, +1, -1}, // tourner droite sur place
  {-1, +1, +1, -1}, // glisser gauche (mecanum)
  {+1, -1, -1, +1}  // glisser droite (mecanum)
};
const char* NOMS[6] = {
  "AVANCER", "RECULER", "TOURNER GAUCHE", "TOURNER DROITE",
  "GLISSER GAUCHE", "GLISSER DROITE"
};

// EXACTEMENT le principe du dernier programme qui fonctionne :
// 50 ms d'arret, puis activation M1, M2, M3, M4 a 75 ms d'intervalle,
// encore 75 ms apres M4, puis 300 ms de marche pour les quatre roues.
// Ici, le temps est gere sans bloquer le serveur Web : STOP reste reactif.
const uint32_t PAUSE_INIT_MS = 50;
const uint32_t ECART_MOTEURS_MS = 75;
const uint32_t ENSEMBLE_MS = 300;

enum PhaseMoteurs { ARRET, DEMARRAGE, MAINTIEN };
PhaseMoteurs phase = ARRET;
int8_t directions[4] = {0, 0, 0, 0};
uint8_t prochainMoteur = 0;
uint32_t prochaineEtape = 0;

void toutArreter() {
  for (int i = 0; i < 4; ++i) {
    digitalWrite(A[i], LOW);
    digitalWrite(B[i], LOW);
  }
  phase = ARRET;
}

void moteur(int i, int8_t direction) {
  digitalWrite(A[i], LOW);
  digitalWrite(B[i], LOW);
  if (direction > 0) digitalWrite(A[i], HIGH);
  if (direction < 0) digitalWrite(B[i], HIGH);
}

void lancerMouvement(uint8_t type) {
  if (type >= 6) return;
  toutArreter();
  for (int i = 0; i < 4; ++i) {
    directions[i] = MOTIFS[type][i] * AVANT[i];
  }
  prochainMoteur = 0;
  prochaineEtape = millis() + PAUSE_INIT_MS;
  phase = DEMARRAGE;
  Serial.print("COMMANDE : ");
  Serial.println(NOMS[type]);
}

void actualiserMoteurs() {
  if (phase == ARRET) return;
  uint32_t maintenant = millis();
  if ((int32_t)(maintenant - prochaineEtape) < 0) return;

  if (phase == DEMARRAGE) {
    moteur(prochainMoteur, directions[prochainMoteur]);
    Serial.printf("M%d : %s HIGH\n", prochainMoteur + 1,
                  directions[prochainMoteur] > 0 ? "A" : "B");
    prochainMoteur++;
    if (prochainMoteur < 4) {
      prochaineEtape = maintenant + ECART_MOTEURS_MS;
    } else {
      phase = MAINTIEN;
      // Le programme valide attendait aussi 75 ms apres M4.
      prochaineEtape = maintenant + ECART_MOTEURS_MS + ENSEMBLE_MS;
    }
  } else if (phase == MAINTIEN) {
    toutArreter();
    Serial.println("STOP AUTO - TOUS MOTEURS LOW");
  }
}

// ------------------------------------------------------------
// LIDAR LD06 - RX = GPIO 33, PWM = GPIO 32
// ------------------------------------------------------------
#if ACTIVER_LIDAR
const int RX_LIDAR = 33;
const int PWM_LIDAR = 32;
LD06 lidar(Serial2, PWM_LIDAR);

// Format conserve de l'ancien programme :
// octets 0..5 : pose x, y, angle (int16 LE, int16 LE, uint16 LE)
// octets 6..7 : nombre de points (uint16 LE)
// puis 5 octets/point : angle centidegres (uint16 LE),
// distance (uint16 LE), intensite (uint8).
const uint16_t MAX_POINTS = 460;
const size_t MAX_OCTETS = 8 + 5 * MAX_POINTS;
uint8_t scanPublie[MAX_OCTETS] = {0};
size_t tailleScan = 0;
uint16_t nombrePoints = 0;
uint32_t dernierScanMs = 0;
int16_t poseX = 0;
int16_t poseY = 0;
uint16_t poseAngle = 0;

void lireLidar() {
  // Priorite aux commandes moteurs pour ne pas prolonger les impulsions.
  if (phase != ARRET || Serial2.available() < 47) return;
  if (!lidar.readScan()) return;
  uint16_t n = lidar.getNbPointsInScan();
  if (!n || n > MAX_POINTS) return;

  size_t pos = 8;
  for (uint16_t i = 0; i < n; ++i) {
    const auto* p = lidar.getPoints(i);
    uint16_t angle = (uint16_t)(p->angle * 100);
    uint16_t distance = p->distance;
    scanPublie[pos++] = angle & 0xFF;
    scanPublie[pos++] = angle >> 8;
    scanPublie[pos++] = distance & 0xFF;
    scanPublie[pos++] = distance >> 8;
    scanPublie[pos++] = p->intensity;
  }
  tailleScan = pos;
  nombrePoints = n;
  dernierScanMs = millis();
}

void envoyerScan() {
  if (!tailleScan) {
    server.send(503, "text/plain", "NO_VALID_SCAN");
    return;
  }
  // Pose renseignee depuis /pose. Ce n'est pas une localisation calculee.
  scanPublie[0] = (uint16_t)poseX & 0xFF;
  scanPublie[1] = (uint16_t)poseX >> 8;
  scanPublie[2] = (uint16_t)poseY & 0xFF;
  scanPublie[3] = (uint16_t)poseY >> 8;
  scanPublie[4] = poseAngle & 0xFF;
  scanPublie[5] = poseAngle >> 8;
  scanPublie[6] = nombrePoints & 0xFF;
  scanPublie[7] = nombrePoints >> 8;
  server.sendHeader("Access-Control-Allow-Origin", "*");
  server.setContentLength(tailleScan);
  server.send(200, "application/octet-stream", "");
  server.client().write(scanPublie, tailleScan);
}

void reglerPose() {
  poseX = (int16_t)constrain(server.arg("x").toInt(), -32768, 32767);
  poseY = (int16_t)constrain(server.arg("y").toInt(), -32768, 32767);
  int a = server.arg("z").toInt();
  poseAngle = (uint16_t)(((a % 36000) + 36000) % 36000);
  server.send(200, "text/plain", "OK");
}
#endif

// ------------------------------------------------------------
// PAGE DE PILOTAGE - TOUCHES + BOUTONS
// Un appui lance une impulsion ; maintien = repetition lente.
// ------------------------------------------------------------
const char PAGE[] PROGMEM = R"HTML(
<!doctype html><html lang="fr"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Robot ESP32 Mecanum LD06</title>
<style>
body{margin:0;padding:16px;background:#152136;color:#fff;font-family:Arial,sans-serif;text-align:center}
main{max-width:500px;margin:auto;background:#263950;padding:18px;border-radius:14px}
h2{color:#89c7fa}button{font-size:22px;color:white;background:#347bd2;border:0;
border-radius:10px;padding:17px 12px;cursor:pointer;touch-action:none;user-select:none}
.grid{display:grid;grid-template-columns:repeat(3,1fr);gap:9px;margin:18px 0}
.stop{background:#d54450}.turn{background:#7654bf}#etat{min-height:30px;padding:12px;
background:#14263a;border-radius:9px;color:#b1f0c4}
small{color:#c4d1e0}a{color:#99d4ff}
</style></head><body><main>
<h2>Robot ESP32 - Mecanum</h2>
<div id="etat">Pret</div>
<div class="grid">
  <span></span><button data-key="ArrowUp">&#8593;</button><span></span>
  <button data-key="ArrowLeft">&#8592;</button>
  <button id="stop" class="stop">STOP</button>
  <button data-key="ArrowRight">&#8594;</button>
  <span></span><button data-key="ArrowDown">&#8595;</button><span></span>
  <button class="turn" data-key="a">&#8634; A</button>
  <span></span><button class="turn" data-key="d">D &#8635;</button>
  <button class="turn" data-key="q">&#8678; Q</button>
  <span></span><button class="turn" data-key="e">E &#8680;</button>
</div>
<p><small>&larr; = tourner gauche, &rarr; = tourner droite.<br>
A et D = tourner. Q et E = deplacement lateral Mecanum.<br>
Maintenir une touche = repetitions courtes. Espace = STOP.<br>
Essais d'abord avec les roues soulevees.</small></p>
<p><small>LiDAR : <a href="/lidar_status" target="_blank">statut</a> |
<a href="/scan" target="_blank">scan binaire</a> |
<a href="/ping" target="_blank">ping</a></small></p>
</main><script>
const routes={ArrowUp:'forward',ArrowDown:'backward',ArrowLeft:'left',ArrowRight:'right',a:'rotateleft',d:'rotateright',q:'strafeleft',e:'straferight'};
const etat=document.getElementById('etat');
let active=null, timer=null, busy=false, generation=0;

async function impulse(key, id){
  if(!active || active!==key || generation!==id || busy)return;
  busy=true;
  try{
    const r=await fetch('/'+routes[key]+'?t='+Date.now(),{cache:'no-store'});
    if(!r.ok)throw Error('HTTP '+r.status);
    if(generation===id)etat.textContent=await r.text();
  }catch(e){
    if(generation===id){etat.textContent='Connexion perdue : '+e.message;arreter();}
  }finally{busy=false;}
}
function arreter(){
  generation++;active=null;clearInterval(timer);timer=null;
  fetch('/stop?t='+Date.now(),{cache:'no-store'}).catch(()=>{});
}
function demarrer(key){
  if(!routes[key] || active===key)return;
  // Ne pas envoyer /stop ici : il pourrait arriver apres /forward
  // et annuler la nouvelle commande (requêtes HTTP concurrentes).
  generation++;clearInterval(timer);timer=null;
  active=key;const id=generation;
  impulse(key,id);
  timer=setInterval(()=>impulse(key,id),750);
}
// Utiliser e.key pour les lettres : fonctionne avec clavier AZERTY et QWERTY.
function touche(e){
  return e.code.startsWith('Arrow') ? e.code : e.key.toLowerCase();
}
document.addEventListener('keydown',e=>{
  if(e.code==='Space'){e.preventDefault();arreter();etat.textContent='STOP';return;}
  const k=touche(e);
  if(routes[k]){e.preventDefault();if(!e.repeat)demarrer(k);}
});
document.addEventListener('keyup',e=>{
  if(active===touche(e)){arreter();etat.textContent='STOP';}
});
document.querySelectorAll('[data-key]').forEach(b=>{
  const key=b.dataset.key;
  b.addEventListener('pointerdown',e=>{e.preventDefault();b.setPointerCapture(e.pointerId);demarrer(key);});
  b.addEventListener('pointerup',()=>{arreter();etat.textContent='STOP';});
  b.addEventListener('pointercancel',()=>{arreter();etat.textContent='STOP';});
});
document.getElementById('stop').addEventListener('click',()=>{arreter();etat.textContent='STOP';});
window.addEventListener('blur',arreter);
window.addEventListener('pagehide',arreter);
</script></body></html>
)HTML";

void routeMouvement(int index) {
  lancerMouvement(index);
  server.sendHeader("Access-Control-Allow-Origin", "*");
  server.send(200, "text/plain; charset=utf-8", String(NOMS[index]) + " : impulsion lancee");
}

void setup() {
  Serial.begin(115200);
  delay(300);

  // Avant la mise en sortie : aucune commande active.
  for (int i = 0; i < 4; ++i) {
    digitalWrite(A[i], LOW);
    digitalWrite(B[i], LOW);
    pinMode(A[i], OUTPUT);
    pinMode(B[i], OUTPUT);
  }
  toutArreter();
  Serial.println("MOTEURS : GPIO initialises a LOW");
  Serial.println("AVANT : M1/M4 inverses, M2/M3 normaux");

  WiFi.mode(WIFI_AP);
  bool ok = WiFi.softAP(WIFI_SSID, WIFI_PASSWORD);
  Serial.println(ok ? "WIFI : OK" : "WIFI : ECHEC");
  Serial.print("IP : "); Serial.println(WiFi.softAPIP());

  server.on("/", HTTP_GET, [](){server.send_P(200,"text/html; charset=utf-8",PAGE);});
  server.on("/ping", HTTP_GET, [](){server.send(200,"text/plain","OK");});
  server.on("/forward", HTTP_GET, [](){routeMouvement(0);});
  server.on("/backward", HTTP_GET, [](){routeMouvement(1);});
  // Fleches gauche/droite = ROTATION (pas glissement lateral).
  server.on("/left", HTTP_GET, [](){routeMouvement(2);});
  server.on("/right", HTTP_GET, [](){routeMouvement(3);});
  server.on("/rotateleft", HTTP_GET, [](){routeMouvement(2);});
  server.on("/rotateright", HTTP_GET, [](){routeMouvement(3);});
  // Q / E pour le deplacement lateral des roues Mecanum.
  server.on("/strafeleft", HTTP_GET, [](){routeMouvement(4);});
  server.on("/straferight", HTTP_GET, [](){routeMouvement(5);});
  server.on("/stop", HTTP_GET, [](){
    toutArreter();Serial.println("STOP MANUEL");server.send(200,"text/plain","STOP");
  });

#if ACTIVER_LIDAR
  Serial2.setRxBufferSize(4096);
  Serial2.begin(230400, SERIAL_8N1, RX_LIDAR, -1);
  Serial2.setTimeout(2);
  lidar.init();
  Serial.println("LIDAR : initialisation demandee sur RX33 / PWM32");
  server.on("/scan", HTTP_GET, envoyerScan);
  server.on("/pose", HTTP_GET, reglerPose);
  server.on("/lidar_status", HTTP_GET, [](){
    String s = String("{\"enabled\":true,\"points\":") + nombrePoints +
      ",\"age_ms\":" + (tailleScan ? String(millis() - dernierScanMs) : String(-1)) + "}";
    server.send(200, "application/json", s);
  });
#else
  server.on("/scan", HTTP_GET, [](){server.send(503,"text/plain","LIDAR_DESACTIVE");});
  server.on("/lidar_status", HTTP_GET, [](){server.send(200,"application/json","{\"enabled\":false}");});
#endif

  server.onNotFound([](){server.send(404,"text/plain","Route inconnue");});
  server.begin();
  Serial.println("SERVEUR PRET : http://192.168.4.1");
}

void loop() {
  server.handleClient();
  actualiserMoteurs();

  // Si le telephone/PC deconnecte completement du point d'acces,
  // stopper immediatement la commande en cours.
  // Une deconnexion du navigateur seul reste couverte par STOP AUTO (< 700 ms).
  static uint32_t derniereVerifWifi = 0;
  if (phase != ARRET && millis() - derniereVerifWifi >= 100) {
    derniereVerifWifi = millis();
    if (WiFi.softAPgetStationNum() == 0) {
      toutArreter();
      Serial.println("STOP SECURITE - CLIENT WIFI DECONNECTE");
    }
  }
#if ACTIVER_LIDAR
  lireLidar();
#endif
  delay(1);
}
