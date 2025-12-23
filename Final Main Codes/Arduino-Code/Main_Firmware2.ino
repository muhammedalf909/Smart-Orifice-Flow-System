#include <Wire.h>
#include <LiquidCrystal_I2C.h>
#include <CapacitiveSensor.h>

// ===================== CONFIG =====================
CapacitiveSensor cs = CapacitiveSensor(4, 2);
LiquidCrystal_I2C lcd(0x27, 16, 2);

const float K_FACTOR  = 0.3656;
const float RHO_FLUID = 1000.0;
const float RHO_MANO  = 1590.0;
const float G         = 9.81;
const float H_MAX     = 0.175;       

// Simulation Arrays (51 Points - Smooth S-Curve)
const int TOTAL_POINTS = 51;
const float H_VALS[TOTAL_POINTS] = {
  0.0000, 0.0010, 0.0035, 0.0075, 0.0130, 0.0200, 0.0285, 0.0380, 0.0485, 0.0595,
  0.0710, 0.0825, 0.0940, 0.1050, 0.1155, 0.1255, 0.1345, 0.1425, 0.1495, 0.1555,
  0.1605, 0.1645, 0.1675, 0.1700, 0.1715, 0.1725, 0.1732, 0.1738, 0.1742, 0.1745,
  0.1747, 0.1748, 0.1749, 0.1750, 0.1750, 0.1750, 0.1750, 0.1750, 0.1750, 0.1750,
  0.1750, 0.1750, 0.1750, 0.1750, 0.1750, 0.1750, 0.1750, 0.1750, 0.1750, 0.1750,
  0.1750
};
const float Q_VALS[TOTAL_POINTS] = {
  0.000, 0.012, 0.022, 0.032, 0.042, 0.052, 0.062, 0.071, 0.081, 0.089,
  0.097, 0.105, 0.112, 0.118, 0.124, 0.130, 0.134, 0.138, 0.141, 0.144,
  0.146, 0.148, 0.150, 0.151, 0.151, 0.152, 0.152, 0.152, 0.153, 0.153,
  0.153, 0.153, 0.153, 0.153, 0.153, 0.153, 0.153, 0.153, 0.153, 0.153,
  0.153, 0.153, 0.153, 0.153, 0.153, 0.153, 0.153, 0.153, 0.153, 0.153,
  0.153
};

long zeroPoint = 0;
bool isRealMode = false;
int simIndex = 0;

void setup() {
  Serial.begin(9600);
  lcd.init(); lcd.backlight();
  cs.set_CS_AutocaL_Millis(0xFFFFFFFF);

  // 1. FAST AUTO-ZERO (Immediate)
  long total = 0;
  for(int i=0; i<10; i++) { total += cs.capacitiveSensor(30); delay(10); }
  zeroPoint = total / 10;
  
  lcd.setCursor(0, 0); 
  lcd.print("S.O.L.I.D"); 
  lcd.setCursor(0, 1);
  lcd.print("Waiting Python");

  // 2. WAIT FOR PYTHON ('S')
  while(Serial.read() != 'S'); 
}

void loop() {
  // 3. 5-SECOND ANALYSIS PHASE (Only Runs Once)
  lcd.clear(); lcd.print("Analyzing...");
  lcd.setCursor(0, 1);
  lcd.print("Wait Pls *-*");
  long validSamples = 0;
  long accumRaw = 0;
  unsigned long startT = millis();
  
  while(millis() - startT < 5000) {
     long r = cs.capacitiveSensor(30);
     long val = r - zeroPoint;
     if (val > 100) { // Threshold for "Wet"
        validSamples++;
        accumRaw += val;
     }
     delay(50);
  }

  // 4. DECISION
  if (validSamples > 10) {
     isRealMode = true; // Sensor detected water
  } else {
     isRealMode = false; // Sensor Dry/Disconnect -> SIMULATION
  }

  // 5. MAIN OPERATION LOOP (Infinite)
  lcd.clear();
  while(true) {
    if (isRealMode) runReal();
    else runSim();
  }
}

void runReal() {
  long r = cs.capacitiveSensor(30);
  long val = r - zeroPoint;
  if(val < 0) val = 0;
  
  float fraction = (float)val / 9000.0; // Calibration span
  if (fraction > 1.0) fraction = 1.0;
  
  float h = fraction * H_MAX;
  float Q = 0;
  if (h > 0) Q = K_FACTOR * sqrt(h);
  
  sendData(Q, h);
  updateDisplay(Q, h, false);
  delay(200);
}

void runSim() {
  float h = H_VALS[simIndex];
  float Q = Q_VALS[simIndex];
  
  sendData(Q, h);
  updateDisplay(Q, h, true); // true = Show '!'
  
  // Advance Index (S-Curve Logic)
  simIndex++;
  if (simIndex >= TOTAL_POINTS) {
    simIndex = TOTAL_POINTS - 1; // Hold at max
    delay(1000); // Hold delay
  }
  delay(1000); // Frame timing (1 second per step)
}

void sendData(float q, float h) {
  // STRICT FORMAT
  Serial.print("Q(L/s): "); Serial.print(q, 4);
  Serial.print(" h_Snap(m): "); Serial.println(h, 4);
}

void updateDisplay(float q, float h, bool isSim) {
  float p = (RHO_MANO - RHO_FLUID) * G * h;
  lcd.setCursor(0, 0);
  if(isSim) lcd.print("!"); else lcd.print(" "); // Indicator
  lcd.print("Q:"); lcd.print(q, 3); lcd.print("L/s");
  
  lcd.setCursor(0, 1);
  lcd.print("h:"); lcd.print(h*100.0, 1); lcd.print("cm P:"); lcd.print((int)p);
}
