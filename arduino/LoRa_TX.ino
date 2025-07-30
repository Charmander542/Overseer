// Feather9x_TX_With_Commands
// -*- mode: C++ -*-
// EDIT: Modified to randomly hop between a user-configurable number of frequencies (up to 50)
// and transmit "test <freq> MHz" at a fixed interval.

// ---- LIBRARIES ----
#include <SPI.h>
#include <RH_RF95.h>
#include <SerialCommand.h>

#define SERIALCOMMAND_HARDWAREONLY


// ---- PIN DEFINITIONS (Unchanged) ----
#if defined (__AVR_ATmega32U4__)
  #define RFM95_CS    8
  #define RFM95_INT   7
  #define RFM95_RST   4
#elif defined(ADAFRUIT_FEATHER_M0) || defined(ADAFRUIT_FEATHER_M0_EXPRESS) || defined(ARDUINO_SAMD_FEATHER_M0)
  #define RFM95_CS    8
  #define RFM95_INT   3
  #define RFM95_RST   4
#elif defined(ARDUINO_ADAFRUIT_FEATHER_RP2040_RFM)
  #define RFM95_CS   16
  #define RFM95_INT  21
  #define RFM95_RST  17
#elif defined(ESP32)
  #define RFM95_CS   33
  #define RFM95_INT  27
  #define RFM95_RST  13
#else
  #error "Board not defined, please add your pin definitions"
#endif


// ---- RADIO CONFIGURATION ----
float current_freq;
#define RF95_SYNC_WORD 0x34


// ---- GLOBAL OBJECTS and VARIABLES ----
RH_RF95 rf95(RFM95_CS, RFM95_INT);
SerialCommand SCmd;
bool is_running = false;

// Non-blocking timer for sending packets
const long packetInterval = 1000; // Send a packet every 1 second
unsigned long previousPacketMillis = 0;

// Non-blocking timer for frequency hopping
unsigned long previousHopMillis = 0;
long hopInterval = 0; // Will be randomized

// EDIT: ---- DYNAMIC FREQUENCY HOPPING CONFIGURATION ----
const int MAX_FREQUENCIES = 50;
int num_active_frequencies = 10; // Default to 10 frequencies, can be changed by user command

// Frequencies are typically 200kHz apart for LoRa in the 915MHz band
const float frequencies[MAX_FREQUENCIES] = {
  902.3, 902.5, 902.7, 902.9, 903.1, 903.3, 903.5, 903.7, 903.9, 904.1, // 1-10
  904.3, 904.5, 904.7, 904.9, 905.1, 905.3, 905.5, 905.7, 905.9, 906.1, // 11-20
  906.3, 906.5, 906.7, 906.9, 907.1, 907.3, 907.5, 907.7, 907.9, 908.1, // 21-30
  908.3, 908.5, 908.7, 908.9, 909.1, 909.3, 909.5, 909.7, 909.9, 910.1, // 31-40
  910.3, 910.5, 910.7, 910.9, 911.1, 911.3, 911.5, 911.7, 911.9, 912.1  // 41-50
};


// --- FORWARD DECLARATIONS for Command Handlers ---
void cmdGo();
void cmdSetHops(); // EDIT: New command
void cmdSetModemConfig();
void cmdHelp();
void unrecognized(const char *command);


// ---- SETUP ----
void setup() {
  pinMode(RFM95_RST, OUTPUT);
  digitalWrite(RFM95_RST, HIGH);

  Serial.begin(115200);
  while (!Serial && millis() < 2000);

  randomSeed(analogRead(A0));
  
  Serial.println("\nFeather LoRa Random Hop TX");
  Serial.println("System is ready. Send 'GO' to start transmitting.");

  // Radio reset and init
  digitalWrite(RFM95_RST, LOW); delay(10); digitalWrite(RFM95_RST, HIGH); delay(10);
  while (!rf95.init()) { Serial.println("LoRa radio init failed"); while (1); }
  Serial.println("LoRa radio init OK!");

  // Perform initial random frequency selection based on the default hop count
  int initial_index = random(0, num_active_frequencies);
  current_freq = frequencies[initial_index];
  if (!rf95.setFrequency(current_freq)) { Serial.println("Initial setFrequency failed"); while (1); }
  Serial.print("Standing by on initial frequency: "); Serial.println(current_freq);
  
  rf95.setTxPower(23, false);
  rf95.spiWrite(0x39, RF95_SYNC_WORD);

  // --- Registering Serial Commands ---
  SCmd.addCommand("GO", cmdGo);
  SCmd.addCommand("set_hops", cmdSetHops); // EDIT: Register new command
  SCmd.addCommand("set_modem", cmdSetModemConfig);
  SCmd.addCommand("help", cmdHelp);
  SCmd.setDefaultHandler(unrecognized);
  
  cmdHelp();
}


// ---- MAIN LOOP ----
void loop() {
  SCmd.readSerial();

  if (is_running) {
    unsigned long currentMillis = millis();

    // --- FREQUENCY HOPPING LOGIC ---
    if (currentMillis - previousHopMillis >= hopInterval) {
      previousHopMillis = currentMillis;

      // EDIT: Select a new random frequency from the *active* pool
      int new_index = random(0, num_active_frequencies);
      current_freq = frequencies[new_index];

      Serial.print("\n--- HOPPING -> New Frequency: ");
      Serial.print(current_freq, 1);
      Serial.println(" MHz ---");

      rf95.setFrequency(current_freq);
      hopInterval = random(2000, 5001); // Next hop in 2-5 seconds
    }

    // --- PACKET TRANSMISSION LOGIC ---
    if (currentMillis - previousPacketMillis >= packetInterval) {
      previousPacketMillis = currentMillis;

      char radiopacket[24]; // e.g., "test 902.3 MHz"
      snprintf(radiopacket, sizeof(radiopacket), "test %.1f MHz", current_freq);

      Serial.print("Sending '");
      Serial.print(radiopacket);
      Serial.println("'");
      
      uint8_t packet_len = strlen(radiopacket) + 1;
      rf95.send((uint8_t *)radiopacket, packet_len);
      rf95.waitPacketSent();

      // (Optional reply logic)
      uint8_t buf[RH_RF95_MAX_MESSAGE_LEN];
      uint8_t len = sizeof(buf);
      if (rf95.waitAvailableTimeout(1000)) { 
        if (rf95.recv(buf, &len)) {
          Serial.print("Got reply: "); Serial.println((char*)buf);
          Serial.print("RSSI: "); Serial.println(rf95.lastRssi(), DEC);
        }
      }
    }
  }
}

// ---- COMMAND HANDLER IMPLEMENTATIONS ----

void cmdGo() {
  if (is_running) {
    Serial.println("System is already running.");
  } else {
    Serial.println("\n>>> GO command received. Starting transmission and frequency hopping. <<<");
    is_running = true;
    
    // Reset timers so actions start relative to the 'GO' command
    unsigned long now = millis();
    previousPacketMillis = now;
    previousHopMillis = now;
    hopInterval = random(2000, 5001); // Schedule the first hop
  }
}

/**
 * @brief EDIT: Handles the 'set_hops <number>' command.
 */
void cmdSetHops() {
  char *arg = SCmd.next();
  if (arg != NULL) {
    int new_hops = atoi(arg);
    if (new_hops >= 1 && new_hops <= MAX_FREQUENCIES) {
      num_active_frequencies = new_hops;
      Serial.print("OK. Number of active hop frequencies set to: ");
      Serial.println(num_active_frequencies);
    } else {
      Serial.print("ERROR: Invalid number. Please enter a value between 1 and ");
      Serial.println(MAX_FREQUENCIES);
    }
  } else {
    Serial.println("ERROR: Missing argument. Usage: set_hops <number>");
  }
}


void cmdSetModemConfig() {
  char *arg = SCmd.next();
  if (arg != NULL) {
    if (strcmp(arg, "fast") == 0) { rf95.setModemConfig(RH_RF95::Bw500Cr45Sf128); Serial.println("Modem set: Fast"); }
    else if (strcmp(arg, "medium") == 0) { rf95.setModemConfig(RH_RF95::Bw125Cr45Sf128); Serial.println("Modem set: Medium"); }
    else if (strcmp(arg, "slow") == 0) { rf95.setModemConfig(RH_RF95::Bw31_25Cr48Sf512); Serial.println("Modem set: Slow"); }
    else if (strcmp(arg, "longrange") == 0) { rf95.setModemConfig(RH_RF95::Bw125Cr48Sf4096); Serial.println("Modem set: Long Range"); }
    else { Serial.println("ERROR: Unknown modem config."); }
  } else { Serial.println("ERROR: Missing modem config argument."); }
}

/**
 * @brief EDIT: Updated help command.
 */
void cmdHelp() {
  Serial.println("\n--- LoRa TX Command Help ---");
  Serial.println("Behavior: Transmits 'test <freq> MHz' every second.");
  Serial.println("          Independently, it hops to a new random frequency every 2-5s.");
  Serial.println("---------------------------------------------------------------");
  Serial.println("GO                   - Start transmitting and frequency hopping.");
  Serial.print("set_hops <1-");
  Serial.print(MAX_FREQUENCIES);
  Serial.println(">  - Set the number of frequencies to hop between.");
  Serial.println("set_modem <config>   - Set modem config (fast, medium, slow, longrange).");
  Serial.println("help                 - Shows this help message.");
  Serial.println("---------------------------------------------------------------");
}

void unrecognized(const char *command) {
  Serial.print("Command not found: '");
  Serial.print(command);
  Serial.println("'. Type 'help' for available commands.");
}
