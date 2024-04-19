/*
 --- Arduino controller for the NRG LCMS connected to RoboChem ---

 Serial Communication:
   Sx=y
   Set variable x to value y. Variable number are integer, values are signed floating point.
   Rx
   Read variable x and print its value to serial.

 Variable list:
   number | acccess     | type        | description
   -------|-------------|-------------|--------------------------
    0     | RESERVED    |             | Serial.parseInt returns 0 on error.
    1     | READ/WRITE  | STRING [20] | Device identifier.
    2     | READ_ONLY   | INT-INT     | Error register 'x-y' x = error type, y = error value. Is reset upon reading.
    3     | COMMAND     | NONE        | Save defaults.
    4     | COMMAND     | NONE        | Factory Reset.
    5     | READ/WRITE  | INT[0-1]    | Valve position. Sends acknowledge signal when done. (0=A, 1=B) 
    6     | COMMAND     | NONE        | Send  'START REQUEST' [ERI Remote Pin #1]. Active = Low.  Request to start injection cycle. Receiver is the autosampler.
    7     | COMMAND     | NONE        | Send  'STOP'          [ERI Remote Pin #2]. Active = Low.  Request to reach system ready state as soon as possible. Receiver is any module performing run-time_of_inj controlled activities.
    8     | READ_ONLY   | INT[1]      | Read  'READY'         [ERI Remote Pin #3]. Active = high. Read system status to check if it is ready for next analysis.
    9     | COMMAND     | NONE        | Send 'Calibrate' command to phase sensor
    10    | READ_ONLY   | FLOAT       | Read phase sensor output
    11    | READ/WRITE  | INT[0-1]    | Set automatic analysis status. 0=OFF, 1=ON 
  
 Error codes:
   type  |  description | value
   ------|--------------|--------------
   0     | No error     | Undefined
   1     | Serial error | Variable number which gave the issue
   2     | Other error  | TODO


 Hardware connections (Arduino nano board):
   Agilent Infinity 1290 II UPLC-MS
   Vici Switch-Valve Control Module
   OCB350 phase sensor board


External Device Pinouts:
  Agilent ERI Remote pinout used for the Infinity 1290 II :
    Pin    | Function       | Color         | Connected
    -------|----------------|---------------|-----------
    1      | Start Request  | White         | YES
    2      | Stop           | Brown         | YES
    3      | Ready          | Green         | YES
    4      | Peak Detect    | Yellow        | NO
    5      | Power On       | Grey          | NO
    6      | Shut Down      | Pink          | NO
    7      | Start          | Blue          | NO
    8      | Prepare        | Red           | NO
    9      | 1Wire Data     | Black         | NO
    10     | Digital Ground | Violet        | YES
    10     | +5V ERI out    | Grey-Pink     | NO
    10     | PGND           | Red-Blue      | NO
    10     | PGND           | White-Green   | NO
    10     | +24V ERI out   | Brown-Green   | NO
    10     | +24V ERI out   | White-Yellow  | NO
    10     | Unused         | Yellow-Brown  | NO


  Vici actuator controller pinout:
    Pin    | Function                      | Connected
    -------|-------------------------------|-----------
    1      | Ground                        | YES
    2      | +5V VDC                       | NO
    3      | Position A out                | NO
    4      | Position B out                | NO
    5      | Position A in                 | YES
    6      | Position B in                 | YES
    7      | Position A relay contact out  | NO
    8      | Position B relay contactout   | NO
    9      | Position A relay contactin    | NO
    10     | Position B relay contactin    | NO


  OCB350 board pinout:
    Pin    | Function    | Color   | Connected
    -------|-------------|---------|-----------
    1      | Vcc         | Red     | YES
    2      | Logic Out A | Orange  | YES
    3      | Logic Out B | Blue    | YES
    4      | Calibrate   | Green   | YES
    5      | Analog Out  | White   | NO
    6      | Ground      | Black   | YES

 Libraries:
   no external libraries.

 Notes:
 -Pins
    Pins 0 and 1 not used as they are also used to transmit serial data.
 -Switch Valve
    Sample loop is filled from the (low pressure) reaction line in position A and then added to the (high pressure) HPLC line in position B
 -Phase Sensor
   Assumed calibration procedure: Place the tubing in the device with no liquid and then run the calibration (takes a second or so).
     pin A - HIGH &  pin B - LOW = Clear Solution
     pin A - LOW &  pin B - HIGH = Empty
     pin A - HIGH &  pin B - HIGH = UNK (Absorbing Sol or Error)
     pin A - LOW &  pin B - LOW = UNK (Absorbing Sol or Error)

  
 Template by Simone Pilon <s.pilon at uva.nl> - Noël Research Group - 2024
 Functions by Olly Bayley <o.m.bayley at uva.nl> - Noël Research Group - 2024
*/

#include <math.h>
#include <EEPROM.h>
#include "Device_id.h"	// Routines to read and write device id.

// LCMS Trigger Pins
#define START_REQUEST_SIGNAL_PIN 2 // Pin to output to ERI Remote Pin #1 (White)
#define STOP_SIGNAL_PIN 3 // Pin to output to ERI Remote Pin #2 (Brown)
#define READY_SIGNAL_PIN 4 // Pin to output to ERI Remote Pin #3 (Green)

// Valve Control Pins
#define VALVE_A_IN_PIN 9  // Pin to to read valve to position A (Vici Pin 3)
#define VALVE_B_IN_PIN 10 // Pin to to read valve to position B (Vici Pin 4)
#define VALVE_A_OUT_PIN 11 // Pin to to set valve to position A (Vici Pin 5)
#define VALVE_B_OUT_PIN 12 // Pin to to set valve to position B (Vici Pin 6)

// Phase Sensor Read Pins
#define PHASE_SENSOR_OUT_A_PIN 6 // Pin to read phase sensor output (Orange)
#define PHASE_SENSOR_OUT_B_PIN 7 // Pin to read phase sensor output (Blue)
#define PHASE_SENSOR_CALIBRATE_PIN 8 // Pin to calibrate phase sensor (Green)

// Error codes (type)
#define ERROR_NO_ERROR 0	  // No error.
#define ERROR_SERIAL 1      // error value is variable number from error.
#define ERROR_PIN 2      	  // See pin.h

// EEPROM
#define EEPROM_ADDRESS_CHECK 0	// 1 byte char
#define DEFAULT_CHECK 42
#define EEPROM_ADDRESS_ID 1	// 20 bytes char[]
#define DEFAULT_ID "LCMS_Controller"
#define EEPROM_ADDRESS_PORTS 21	// 1 byte int
#define DEFAULT_NUM_SWITCH_PORTS 6

// Global variables
  // Error Handling
uint8_t error_type = 0;
uint8_t error_value = 0;
  // LCMS
uint8_t lcms_ready_state = 0;
  // Switch Valve
uint8_t num_switch_ports = DEFAULT_NUM_SWITCH_PORTS;
uint8_t valve_position = 0;
  // Phase Sensor
uint8_t phase_sensor_a_pin = 0;
uint8_t phase_sensor_b_pin = 0;
  //General Program Variables
uint8_t auto_analysis = 0;
uint8_t slug_sampled = 0;
long time_of_inj = 0;
int sampling_delay = 30000;

//-----General Methods-----
/**
 * Load stored values from EEPROM to system
 */
void load_defaults()
{
	uint8_t charvalue = 0;
	EEPROM.get(EEPROM_ADDRESS_CHECK, charvalue);
	if (charvalue == DEFAULT_CHECK)
	{
    EEPROM.get(EEPROM_ADDRESS_PORTS, num_switch_ports);
		eeprom_get_id(EEPROM_ADDRESS_ID);
	}
	else
	{
		factory_reset();
	}
}

/**
 * Store values from system to EEPROM as defaults
 */
void store_defaults()
{
  EEPROM.put(EEPROM_ADDRESS_PORTS, num_switch_ports);
	eeprom_put_id(EEPROM_ADDRESS_ID);
}

/**
 * Reset stored values to original defaults
 */
void factory_reset()
{
  num_switch_ports = DEFAULT_NUM_SWITCH_PORTS;
	EEPROM.put(EEPROM_ADDRESS_PORTS, num_switch_ports);
	uint8_t charvalue = DEFAULT_CHECK;
	EEPROM.put(EEPROM_ADDRESS_CHECK, charvalue);
	init_id(DEFAULT_ID);
	eeprom_put_id(EEPROM_ADDRESS_ID);
}

/**
 * Retruns true if solution is in the phase sensor tubing, return false if no solution is in the tubing
 */
bool loop_full(){
  if(valve_position == 1){
    return false;
  }
  if(digitalRead(PHASE_SENSOR_OUT_A_PIN) == HIGH && digitalRead(PHASE_SENSOR_OUT_B_PIN) == LOW){
    return true;
  }
  if(digitalRead(PHASE_SENSOR_OUT_A_PIN) == HIGH && digitalRead(PHASE_SENSOR_OUT_B_PIN) == HIGH){
    return true;
  } 
  return false;
}

/**
 * Samples reaction mixture
 */
void sample_reaction_stream(){
  //Set to position B (sample loop in high pressure line)
  digitalWrite(VALVE_A_OUT_PIN, HIGH);
  digitalWrite(VALVE_B_OUT_PIN, LOW);
  delay(2000);
  //return to position A (sample loop in low pressure line)
  digitalWrite(VALVE_A_OUT_PIN, LOW);
  digitalWrite(VALVE_B_OUT_PIN, HIGH);
}

/**
 * Sends startpulse to LCMS
 */
void start_analysis(){
  digitalWrite(START_REQUEST_SIGNAL_PIN, LOW); // Set to LOW (0V)
  delay(100);
  digitalWrite(START_REQUEST_SIGNAL_PIN, HIGH); // Return to HIGH (5V)
}

void read_valve_pos(){
  if (digitalRead(VALVE_A_IN_PIN) == LOW && digitalRead(VALVE_B_IN_PIN) == HIGH){
    valve_position = 0;
  }else if (digitalRead(VALVE_A_IN_PIN) == HIGH && digitalRead(VALVE_B_IN_PIN) == LOW){
    valve_position = 1;
  }else{
    valve_position = 2;
  }

void read_phase_sensor(){
  // TODO add a time averaged/smoothed way to read the pahse sensor that dosen't trigger upon droplets
}

//-----Serial Response Methods-----
/**
 * Checks serial line for commands and executes them.
 */
void parse_serial()
{
	while (Serial.available() > 0)
	{
		char command = Serial.read();
		int variable_number = 0;

		if (command == 'R' || command == 'r')  // Comands to READ and return info to caller
		{
			// Read variable
			variable_number = Serial.parseInt();
			switch (variable_number)
			{
				case 1:
					// Device identifier
					Serial.println(device_id);
					break;
				case 2:
					// Error register
					Serial.print(error_type);
					Serial.print('-');
					Serial.println(error_value);
					error_type = ERROR_NO_ERROR;
					error_value = 0;
					break;
        case 5:
					// Switch Valve Position TODO connect to actuator pins to read position rather than track
          read_valve_pos();
					Serial.println(valve_position);
					break;
        case 8:
          // LCMS ready state
          lcms_ready_state = digitalRead(READY_SIGNAL_PIN);
          if(lcms_ready_state == HIGH){
            Serial.println("READY");
          }else {
            Serial.println("NOT READY");
          }
        break;
        case 10:
          // Phase sensor state
          phase_sensor_a_pin = digitalRead(PHASE_SENSOR_OUT_A_PIN);
          phase_sensor_b_pin = digitalRead(PHASE_SENSOR_OUT_B_PIN);
          if(phase_sensor_a_pin == HIGH && phase_sensor_b_pin == LOW){
            Serial.println("Clear Solution");
          }else if(phase_sensor_a_pin == LOW && phase_sensor_b_pin == HIGH){
            Serial.println("Empty");
          }else if(phase_sensor_a_pin == HIGH && phase_sensor_b_pin == HIGH){
            Serial.println("Absorbing Solution");
          }else {
            Serial.println("Error");
          }
        break;
        case 11:
           Serial.println(auto_analysis);
        break;
				default:
					// Syntax errors11=0

					error_type = ERROR_SERIAL;
					error_value = variable_number;
					break;
			}

// TODO you can check for errors and set the global variables here
//			if (Gpio_pin::error != GPIO_ERROR_OK)
//			{
//				error_type = ERROR_PIN;
//				error_value = Gpio_pin::error;
//				Gpio_pin::error = GPIO_ERROR_OK;
//			}

		}
		else if (command == 'S' || command == 's')  // Comands to SEND 
		{
			// Write variable
			variable_number = Serial.parseInt();
			Serial.read();
			int variable_value_int = 0;
			float variable_value_float = 0;
      int step = 0;
			// Write device-wide variable
			switch (variable_number)
			{
				case 1:
					// Device identifier
					serial_read_id();
					break;
				case 3:
					// Save defaults
					store_defaults();
					break;
				case 4:
					// Factory reset
					factory_reset();
					break;
        case 5:
					// Set valve position
          variable_value_int = Serial.parseInt();
          read_valve_pos();
					if (variable_value_int == valve_position){
            Serial.println("n (Valve already in position)");
            break;
          }
          if (variable_value_int == 0){ //Set position to A
            digitalWrite(VALVE_A_OUT_PIN, LOW);
            digitalWrite(VALVE_B_OUT_PIN, HIGH);
            Serial.println("k");
          }
          if (variable_value_int == 1){ //Set position to B
            digitalWrite(VALVE_A_OUT_PIN, HIGH);
            digitalWrite(VALVE_B_OUT_PIN, LOW);
            Serial.println("k");
          }
					break;
        case 6:
          // Send START REQUEST through START_REQUEST_SIGNAL_PIN
          variable_value_int = Serial.parseInt();
					if (variable_value_int == 1)
          {
          digitalWrite(START_REQUEST_SIGNAL_PIN, LOW); // Set to LOW (0V)
          delay(100);
          digitalWrite(START_REQUEST_SIGNAL_PIN, HIGH); // Return to HIGH (5V)
          Serial.println("k (Start Request Sent)");
          }
          else
          {
            Serial.println("Unrecognised Command Value");
          }
          break;
        case 7:
          // Send STOP through STOP_SIGNAL_PIN
          variable_value_int = Serial.parseInt();
					if (variable_value_int == 1)
          {
          digitalWrite(STOP_SIGNAL_PIN, LOW); // Set to LOW (0V)
          delay(100);
          digitalWrite(STOP_SIGNAL_PIN, HIGH); // Return to HIGH (5V)
          }
          else
          {
            Serial.println("Unrecognised Command Value");
          }
          break;
          case 9:
          // Send Calibrate
          digitalWrite(PHASE_SENSOR_CALIBRATE_PIN, LOW); // Set to LOW (0V)
          delay(100);
          digitalWrite(PHASE_SENSOR_CALIBRATE_PIN, HIGH); // Return to HIGH (5V)
          break;
          case 11:
            variable_value_int = Serial.parseInt();
            if (variable_value_int > 1){
              Serial.println("Unrecognised Command Value");
            } else{
              auto_analysis = variable_value_int;
            }
          break;
				default:
					// Syntax error
					error_type = ERROR_SERIAL;
					error_value = variable_number;
					break;
          
			}

			// TODO you can check for errors and set the global variables here
			// if (Gpio_pin::error != GPIO_ERROR_OK)
			// {
			// 	error_type = ERROR_PIN;
			// 	error_value = Gpio_pin::error;
			// 	Gpio_pin::error = GPIO_ERROR_OK;
			// }
		}
	}
}

//-----Arduino Behaviour Methods-----
// This is run once when the Arduino is powered up.
void setup()
{
	// Load stored values from EEPROM
	load_defaults();
	
	// Initialize LCMS Trigger Pins
  digitalWrite(START_REQUEST_SIGNAL_PIN, HIGH);  // Set to LCMS defaults on startup to prevent triggering upon conection init
  digitalWrite(STOP_SIGNAL_PIN, HIGH);           // Set to LCMS defaults on startup to prevent triggering upon conection init
	digitalWrite(READY_SIGNAL_PIN, LOW);           // Set to LCMS defaults on startup to prevent triggering upon conection init
  pinMode(START_REQUEST_SIGNAL_PIN, OUTPUT);
  pinMode(STOP_SIGNAL_PIN, OUTPUT);
  pinMode(READY_SIGNAL_PIN, INPUT);

  // Initialize Switch Pins
  digitalWrite(VALVE_A_OUT_PIN, LOW);  // Set valve to Position A upon startup
  digitalWrite(VALVE_B_OUT_PIN, HIGH); // Set valve to Position A upon startup
  pinMode(VALVE_A_OUT_PIN, OUTPUT);
  pinMode(VALVE_B_OUT_PIN, OUTPUT);
  pinMode(VALVE_A_IN_PIN, INPUT);
  pinMode(VALVE_B_IN_PIN, INPUT);

  // Initialize Phase Sensor Pins
  pinMode(PHASE_SENSOR_OUT_A_PIN, INPUT);
  pinMode(PHASE_SENSOR_OUT_B_PIN, INPUT);
  pinMode(PHASE_SENSOR_CALIBRATE_PIN, OUTPUT);
  
  //Read in current switch valve positionread();
  read_valve_pos();  // Ensure 

	// Initialize Serial interface
	Serial.begin(9600);
}

// This is run in a loop constantly during execution.
void loop()
{
	while (true)
	{
		parse_serial();
    /*
    Checks that: Auto analysis is enabled, Whether the reaction has already been sampled (stops resampling of parked slug),
    If the loop has been filled (assumes no sampling has already taken place on the slug), If sufficient time has been given since the last injection (prevents droplets retriggering the run when clearing the slug)
    */
    if(auto_analysis == 1 && slug_sampled == 0 && loop_full() && millis()-time_of_inj > sampling_delay){
      Serial.println("SAMPLE DETECTED");
      start_analysis();
      delay(5000); // Delay to give LCMS time_of_inj to prepare istd injection
      sample_reaction_stream();
      time_of_inj = millis();
      slug_sampled = 1; //Stops resampling of the same reaction slug
    }
    if(slug_sampled == 1 && digitalRead(PHASE_SENSOR_OUT_A_PIN) == LOW && digitalRead(PHASE_SENSOR_OUT_B_PIN) == HIGH){
      Serial.println("GAS DETECTED");
      slug_sampled = 0; //resets the slug_sampled variable once gas is detected in the line
    }
	}
}
