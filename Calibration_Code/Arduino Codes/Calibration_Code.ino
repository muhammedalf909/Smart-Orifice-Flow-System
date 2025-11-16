#include <CapacitiveSensor.h>

// ============= CONFIGURATION =============
#define SEND_PIN        4
#define SENSE_PIN       2
#define BAUD_RATE       9600
#define SAMPLE_SIZE     30        // Capacitive sensor sampling
#define SAMPLE_RATE     250       // ms between readings (4 Hz)
#define CALIB_DURATION  180000    // 3 minutes in milliseconds

// EMA filter parameter (0.0 - 1.0, lower = smoother)
const float EMA_ALPHA = 0.1;

// ============= GLOBALS =============
CapacitiveSensor capacitiveSensor = CapacitiveSensor(SEND_PIN, SENSE_PIN);

// Filter state
float filteredValue = 0.0;

// Timing
unsigned long calibStartTime = 0;

// Statistics
long maxReading = 0;
long minReading = 999999;
long sumReadings = 0;
unsigned int sampleCount = 0;

// ============= FUNCTION DECLARATIONS =============
void initializeSensor();
void stabilizeFilter();
void collectData();
void printCalibrationResults();


// ============= SETUP =============
void setup() {
  Serial.begin(BAUD_RATE);
  
  // Wait for serial connection
  while (!Serial && millis() < 3000) {
    ; // Wait up to 3 seconds
  }
  
  Serial.println(F("=================================================="));
  Serial.println(F("  VENTURI METER CALIBRATION - ARDUINO SIDE"));
  Serial.println(F("=================================================="));
  Serial.println(F("Initializing capacitive sensor..."));
  
  initializeSensor();
  stabilizeFilter();
  
  Serial.println();
  Serial.println(F("Calibration starting..."));
  Serial.println(F("Duration: 180 seconds (3 minutes)"));
  Serial.println();
  Serial.println(F("CSV_HEADER"));
  Serial.println(F("Sample,Time_s,Raw,Filtered"));
  Serial.println(F("CSV_DATA_START"));
  
  calibStartTime = millis();
}


// ============= MAIN LOOP =============
void loop() {
  unsigned long elapsedTime = millis() - calibStartTime;
  
  // Check if calibration period is complete
  if (elapsedTime >= CALIB_DURATION) {
    Serial.println(F("CSV_DATA_END"));
    Serial.println();
    printCalibrationResults();
    
    // Halt execution
    while (true) {
      delay(5000);
    }
  }
  
  // Collect and process data
  collectData();
  
  // Delay for next sample
  delay(SAMPLE_RATE);
}


// ============= FUNCTIONS =============

/**
 * Initialize sensor with basic settings
 */
void initializeSensor() {
  // Disable autocalibration for consistent baseline
  capacitiveSensor.set_CS_AutocaL_Millis(0xFFFFFFFF);
  
  // Take initial reading to seed filter
  long initialReading = capacitiveSensor.capacitiveSensor(SAMPLE_SIZE);
  
  if (initialReading < 0) {
    Serial.println(F("WARNING: Sensor read error during init"));
    filteredValue = 0;
  } else {
    filteredValue = (float)initialReading;
  }
  
  Serial.print(F("Initial reading: "));
  Serial.println(filteredValue);
}


/**
 * Stabilize EMA filter with multiple readings
 */
void stabilizeFilter() {
  Serial.println(F("Stabilizing filter (20 samples)..."));
  
  for (int i = 0; i < 20; i++) {
    long reading = capacitiveSensor.capacitiveSensor(SAMPLE_SIZE);
    
    if (reading >= 0) {
      // Apply EMA filter
      filteredValue = (EMA_ALPHA * reading) + ((1.0 - EMA_ALPHA) * filteredValue);
    }
    
    delay(100);
  }
  
  Serial.print(F("Filter stabilized at: "));
  Serial.println((long)filteredValue);
}


/**
 * Collect single data point and update statistics
 */
void collectData() {
  // Read raw sensor value
  long rawReading = capacitiveSensor.capacitiveSensor(SAMPLE_SIZE);
  
  // Handle sensor errors
  if (rawReading < 0) {
    // Use previous filtered value if read fails
    rawReading = (long)filteredValue;
  }
  
  // Apply EMA filter
  filteredValue = (EMA_ALPHA * rawReading) + ((1.0 - EMA_ALPHA) * filteredValue);
  long filteredInt = (long)filteredValue;
  
  // Update statistics
  sampleCount++;
  sumReadings += filteredInt;
  
  if (filteredInt > maxReading) {
    maxReading = filteredInt;
  }
  
  if (filteredInt < minReading) {
    minReading = filteredInt;
  }
  
  // Output CSV format
  unsigned long elapsedSeconds = (millis() - calibStartTime) / 1000;
  
  Serial.print(sampleCount);
  Serial.print(F(","));
  Serial.print(elapsedSeconds);
  Serial.print(F(","));
  Serial.print(rawReading);
  Serial.print(F(","));
  Serial.println(filteredInt);
}


/**
 * Print final calibration results with statistics
 */
void printCalibrationResults() {
  // Prevent division by zero
  long avgReading = (sampleCount > 0) ? (sumReadings / sampleCount) : 0;
  long rangeReading = maxReading - minReading;
  
  Serial.println(F("=================================================="));
  Serial.println(F("  CALIBRATION COMPLETE"));
  Serial.println(F("=================================================="));
  Serial.println();
  
  Serial.println(F("Statistics:"));
  Serial.println(F("--------------------------------------------------"));
  Serial.print(F("  Total Samples:  "));
  Serial.println(sampleCount);
  Serial.print(F("  MIN Reading:    "));
  Serial.println(minReading);
  Serial.print(F("  MAX Reading:    "));
  Serial.println(maxReading);
  Serial.print(F("  AVERAGE:        "));
  Serial.println(avgReading);
  Serial.print(F("  RANGE:          "));
  Serial.println(rangeReading);
  Serial.println();
  
  Serial.println(F("Calibration Constants:"));
  Serial.println(F("--------------------------------------------------"));
  Serial.print(F("const long SENSOR_RAW_MIN = "));
  Serial.print(minReading);
  Serial.println(F(";"));
  
  Serial.print(F("const long SENSOR_RAW_MAX = "));
  Serial.print(maxReading);
  Serial.println(F(";"));
  
  Serial.println(F("const float H_MAX_METERS = ???;  // MEASURE MANUALLY"));
  Serial.println();
  
  Serial.println(F("Next Steps:"));
  Serial.println(F("--------------------------------------------------"));
  Serial.println(F("  1. Physically measure H_max with ruler/caliper"));
  Serial.println(F("  2. Copy above constants to main code"));
  Serial.println(F("  3. Upload main code and test system"));
  Serial.println(F("=================================================="));
  Serial.println();
  Serial.println(F("CALIBRATION_DONE"));
}
