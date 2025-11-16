#include <Wire.h>
#include <LiquidCrystal_I2C.h>
#include <CapacitiveSensor.h>


// ==================================================================
// CONFIGURATION SECTION
// Modify these values based on your system calibration
// ==================================================================

// --- Sensor Calibration ---
// Obtain from calibration code output
const long SENSOR_RAW_MIN = 510;       // Minimum sensor reading (no flow)
const long SENSOR_RAW_MAX = 9230;      // Maximum sensor reading (max flow)
const float H_MAX_METERS = 0.145;      // Maximum manometer height (meters)

// --- Venturi Tube Geometry ---
// Measure inner diameters precisely
const float PIPE_D1_METERS = 0.0254;   // Wide section diameter (1" = 25.4mm)
const float PIPE_D2_METERS = 0.0127;   // Narrow section diameter (0.5" = 12.7mm)

// --- Fluid Properties ---
const float FLUID_DENSITY = 1000.0;    // Water density (kg/m³)
const float MANOMETER_DENSITY = 1.225; // Air for inverted manometer (kg/m³)
                                        // Use ~850.0 for oil in U-tube

// --- Flow Coefficient ---
const float DISCHARGE_COEFF = 0.97;    // Empirical coefficient (0.95-0.98)

// --- Filter Settings ---
const float EMA_ALPHA = 0.1;           // Smoothing factor (lower = smoother)

// --- Detection Threshold ---
const float MIN_FLOW_HEIGHT = 0.001;   // Minimum Δh for flow detection (m)

// --- Fallback System ---
const long EXTREME_MIN = 0;            // Sensor lower bound
const long EXTREME_MAX = 15000;        // Sensor upper bound
const int MAX_FAILURES = 5;            // Failed reads before fallback mode


// ==================================================================
// REALISTIC HEIGHT VALUES FOR SNAPPING
// Adjust array based on expected operating range
// ==================================================================
const float HEIGHT_STEPS[] = {
  0.000,  // 0.0 cm - no flow
  0.010,  // 1.0 cm
  0.020,  // 2.0 cm
  0.030,  // 3.0 cm
  0.040,  // 4.0 cm
  0.050,  // 5.0 cm
  0.060,  // 6.0 cm
  0.070,  // 7.0 cm
  0.080,  // 8.0 cm
  0.090,  // 9.0 cm
  0.100,  // 10.0 cm
  0.110,  // 11.0 cm
  0.120,  // 12.0 cm
  0.130,  // 13.0 cm
  0.140,  // 14.0 cm
  0.145   // 14.5 cm - maximum
};

const int HEIGHT_STEPS_COUNT = sizeof(HEIGHT_STEPS) / sizeof(HEIGHT_STEPS[0]);


// ==================================================================
// PHYSICAL CONSTANTS (DO NOT MODIFY)
// ==================================================================
const float GRAVITY = 9.81;            // Gravitational acceleration (m/s²)
const float DENSITY_DIFF = FLUID_DENSITY - MANOMETER_DENSITY;


// ==================================================================
// PRE-CALCULATED CONSTANTS (DO NOT MODIFY)
// ==================================================================
const float AREA_1 = PI * pow(PIPE_D1_METERS / 2.0, 2);
const float AREA_2 = PI * pow(PIPE_D2_METERS / 2.0, 2);
const float AREA_RATIO_SQ = pow(AREA_2 / AREA_1, 2);
const float FLOW_CONSTANT = DISCHARGE_COEFF * AREA_2 * 
                            sqrt((2.0 / FLUID_DENSITY) / (1.0 - AREA_RATIO_SQ));


// ==================================================================
// HARDWARE INSTANCES
// ==================================================================
LiquidCrystal_I2C display(0x27, 16, 2);        // Try 0x3F if 0x27 fails
CapacitiveSensor capacitiveSensor(4, 2);       // Send: D4, Sense: D2


// ==================================================================
// GLOBAL STATE VARIABLES
// ==================================================================
float filteredReading = 0.0;           // EMA filter state
float lastValidHeight = 0.0;           // Last valid Δh for fallback
int failureCount = 0;                  // Consecutive failed reads
bool inFallbackMode = false;           // Fallback status flag


// ==================================================================
// FUNCTION PROTOTYPES
// ==================================================================
void initializeSystem();
void stabilizeFilter(int samples);
bool validateReading(long rawValue);
float snapToRealisticValue(float calculatedHeight);
float calculateFlowRate(float height);
void displayData(float flowRate, float height, float pressure);
void outputSerialData(long raw, bool valid, float hCalc, float hSnap, 
                      float pressure, float flowRate);


// ==================================================================
// SETUP - SYSTEM INITIALIZATION
// ==================================================================
void setup() {
  // Initialize serial communication
  Serial.begin(9600);
  while (!Serial && millis() < 3000) {
    ; // Wait for serial or timeout after 3 seconds
  }
  
  // Initialize LCD
  display.init();
  display.backlight();
  
  // Welcome screen
  display.setCursor(0, 0);
  display.print(F("Venturi v4.0"));
  display.setCursor(0, 1);
  display.print(F("Initializing..."));
  
  Serial.println(F("=================================================="));
  Serial.println(F("  VENTURI FLOWMETER v4.0 - PRODUCTION SYSTEM"));
  Serial.println(F("=================================================="));
  Serial.println();
  
  initializeSystem();
  
  Serial.println(F("System ready. Starting measurements..."));
  Serial.println();
  
  delay(1500);
  display.clear();
}


// ==================================================================
// MAIN LOOP - DATA ACQUISITION AND PROCESSING
// ==================================================================
void loop() {
  // --- Step 1: Read Sensor ---
  long rawValue = capacitiveSensor.capacitiveSensor(30);
  bool isValid = validateReading(rawValue);
  
  float heightCalculated = 0.0;
  float heightSnapped = 0.0;
  float pressureDiff = 0.0;
  float flowRate = 0.0;
  
  // --- Step 2: Process Reading ---
  if (isValid) {
    // Normal operation mode
    failureCount = 0;
    
    // Exit fallback if previously active
    if (inFallbackMode) {
      inFallbackMode = false;
      Serial.println(F("\n✓ Normal operation restored\n"));
    }
    
    // Apply EMA filter
    filteredReading = (EMA_ALPHA * rawValue) + 
                      ((1.0 - EMA_ALPHA) * filteredReading);
    
    // Clamp to calibrated range
    float clampedValue = constrain(filteredReading, SENSOR_RAW_MIN, SENSOR_RAW_MAX);
    
    // Map to height (linear interpolation)
    float normalizedValue = (clampedValue - SENSOR_RAW_MIN) / 
                            (float)(SENSOR_RAW_MAX - SENSOR_RAW_MIN);
    heightCalculated = normalizedValue * H_MAX_METERS;
    
    // Snap to realistic value
    heightSnapped = snapToRealisticValue(heightCalculated);
    
    // Store as last valid measurement
    lastValidHeight = heightSnapped;
    
  } else {
    // Fallback mode for invalid readings
    failureCount++;
    
    if (!inFallbackMode && failureCount >= MAX_FAILURES) {
      inFallbackMode = true;
      Serial.println(F("\n⚠ FALLBACK MODE ACTIVATED"));
      Serial.println(F("→ Using last valid measurement\n"));
    }
    
    // Use last known valid value
    heightSnapped = lastValidHeight;
    heightCalculated = heightSnapped;
  }
  
  // --- Step 3: Calculate Pressure Difference ---
  // Formula: ΔP = (ρ_fluid - ρ_manometer) × g × Δh
  pressureDiff = DENSITY_DIFF * GRAVITY * heightSnapped;
  if (pressureDiff < 0.0) {
    pressureDiff = 0.0;
  }
  
  // --- Step 4: Calculate Flow Rate ---
  flowRate = calculateFlowRate(heightSnapped);
  
  // --- Step 5: Display Results ---
  displayData(flowRate, heightSnapped, pressureDiff);
  
  // --- Step 6: Serial Output ---
  outputSerialData(rawValue, isValid, heightCalculated, heightSnapped, 
                   pressureDiff, flowRate);
  
  // Sampling interval (4 Hz)
  delay(250);
}


// ==================================================================
// INITIALIZATION FUNCTIONS
// ==================================================================

/**
 * Initialize system and seed filter
 */
void initializeSystem() {
  Serial.println(F("Initializing capacitive sensor..."));
  
  // Disable sensor auto-calibration for stable baseline
  capacitiveSensor.set_CS_AutocaL_Millis(0xFFFFFFFF);
  
  // Take initial reading
  long initialValue = capacitiveSensor.capacitiveSensor(30);
  
  if (validateReading(initialValue)) {
    filteredReading = (float)initialValue;
    Serial.print(F("✓ Initial reading: "));
    Serial.println(initialValue);
  } else {
    // Use midpoint as fallback
    filteredReading = (SENSOR_RAW_MIN + SENSOR_RAW_MAX) / 2.0;
    Serial.println(F("⚠ Invalid initial reading"));
    Serial.print(F("→ Using default: "));
    Serial.println((long)filteredReading);
  }
  
  // Stabilize filter with multiple samples
  Serial.println(F("Stabilizing filter..."));
  stabilizeFilter(20);
  
  Serial.print(F("✓ Filter stabilized at: "));
  Serial.println((long)filteredReading);
  Serial.println();
}


/**
 * Stabilize EMA filter with sample readings
 */
void stabilizeFilter(int samples) {
  for (int i = 0; i < samples; i++) {
    long reading = capacitiveSensor.capacitiveSensor(30);
    
    if (reading >= 0) {
      filteredReading = (EMA_ALPHA * reading) + 
                        ((1.0 - EMA_ALPHA) * filteredReading);
    }
    
    delay(100);
  }
}


// ==================================================================
// VALIDATION AND PROCESSING FUNCTIONS
// ==================================================================

/**
 * Validate sensor reading for anomalies
 * Returns: true if reading is acceptable
 */
bool validateReading(long rawValue) {
  // Check extreme bounds
  if (rawValue < EXTREME_MIN || rawValue > EXTREME_MAX) {
    return false;
  }
  
  // Check for sudden jumps (>50% of range)
  if (filteredReading > 0) {
    long delta = abs(rawValue - (long)filteredReading);
    long maxDelta = (SENSOR_RAW_MAX - SENSOR_RAW_MIN) * 0.5;
    
    if (delta > maxDelta) {
      return false;
    }
  }
  
  return true;
}


/**
 * Snap calculated height to nearest realistic value
 * Reduces noise and provides stable readings
 */
float snapToRealisticValue(float calculatedHeight) {
  float minDifference = 1000.0;
  float nearestValue = calculatedHeight;
  
  for (int i = 0; i < HEIGHT_STEPS_COUNT; i++) {
    float difference = abs(calculatedHeight - HEIGHT_STEPS[i]);
    
    if (difference < minDifference) {
      minDifference = difference;
      nearestValue = HEIGHT_STEPS[i];
    }
  }
  
  return nearestValue;
}


/**
 * Calculate volumetric flow rate from manometer height
 * Formula: Q = C_d × A_2 × √(2ΔP / ρ_f / (1 - (A_2/A_1)²))
 * Returns: Flow rate in liters per second
 */
float calculateFlowRate(float height) {
  // No flow below threshold
  if (height < MIN_FLOW_HEIGHT) {
    return 0.0;
  }
  
  // Calculate pressure difference
  float pressureDiff = DENSITY_DIFF * GRAVITY * height;
  
  if (pressureDiff < 0.0) {
    pressureDiff = 0.0;
  }
  
  // Calculate flow rate (m³/s)
  float flowRateCubicMeters = FLOW_CONSTANT * sqrt(pressureDiff);
  
  // Convert to L/s
  float flowRateLiters = flowRateCubicMeters * 1000.0;
  
  return flowRateLiters;
}


// ==================================================================
// OUTPUT FUNCTIONS
// ==================================================================

/**
 * Update LCD display with current measurements
 */
void displayData(float flowRate, float height, float pressure) {
  display.clear();
  
  // Line 1: Flow rate
  display.setCursor(0, 0);
  display.print(F("Q:"));
  display.print(flowRate, 3);
  display.print(F(" L/s"));
  
  // Warning indicator if in fallback mode
  if (inFallbackMode) {
    display.setCursor(15, 0);
    display.print(F("!"));
  }
  
  // Line 2: Height and pressure
  display.setCursor(0, 1);
  display.print(F("h:"));
  display.print(height * 100.0, 1);  // Convert to cm
  display.print(F("cm"));
  
  // Show pressure if space available
  float heightCm = height * 100.0;
  if (heightCm < 10.0) {
    display.setCursor(10, 1);
    display.print(F("P:"));
    display.print(pressure, 0);
  }
}


/**
 * Output detailed data to serial for logging/debugging
 */
void outputSerialData(long raw, bool valid, float hCalc, float hSnap, 
                      float pressure, float flowRate) {
  Serial.print(F("Raw: "));
  Serial.print(raw);
  Serial.print(F(" | Valid: "));
  Serial.print(valid ? F("YES") : F("NO "));
  Serial.print(F(" | Filtered: "));
  Serial.print(filteredReading, 0);
  Serial.print(F(" | h_Calc(m): "));
  Serial.print(hCalc, 6);
  Serial.print(F(" | h_Snap(m): "));
  Serial.print(hSnap, 6);
  Serial.print(F(" | ΔP(Pa): "));
  Serial.print(pressure, 2);
  Serial.print(F(" | Q(L/s): "));
  Serial.print(flowRate, 4);
  
  if (inFallbackMode) {
    Serial.print(F(" [FALLBACK]"));
  }
  
  Serial.println();
}
