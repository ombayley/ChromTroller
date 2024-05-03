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
    8     | READ_ONLY   | INT[1]      | Read  'READY'         [ERI Remote Pin #3]. Active = high. Read system status to check if it is ready for next analysis. TODO have constant monitor to check if achieved and reset upon submit
    9     | COMMAND     | NONE        | Send 'Calibrate' command to phase sensor
    10    | READ_ONLY   | FLOAT       | Read phase sensor output
  
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
    11     | +5V ERI out    | Grey-Pink     | NO
    12     | PGND           | Red-Blue      | NO
    13     | PGND           | White-Green   | NO
    14     | +24V ERI out   | Brown-Green   | NO
    15     | +24V ERI out   | White-Yellow  | NO
    10     | Unused         | Yellow-Brown  | NO


  Vici actuator controller pinout:
    Pin    | Function                      | Connected
    -------|-------------------------------|-----------
    1      | Ground                        | YES
    2      | +5V VDC out                   | NO
    3      | Position A out                | YES
    4      | Position B out                | YES
    5      | Position A in                 | YES
    6      | Position B in                 | YES
    7      | Position A relay contact out  | NO
    8      | Position B relay contactout   | NO
    9      | Position A relay contactin    | NO
    10     | Position B relay contactin    | NO


  OCB350 board pinout:
    Pin    | Function    | Color   | Connected
    -------|-------------|---------|-----------
    1      | VDC         | Red     | YES
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

  -Switch:
     2 - 1 - 6
     |       |
     |       |
     3 - 4 - 5
    1 = Input
    2 = Waste
    3 + 6 = Filling loop
    4 = To LCMS
    5 = From LCMS Pump

    Postion A (0) = 1+6 2+3 4+5
    Postion B (1) = 1+2 3+4 5+6
  
 Template by Simone Pilon <s.pilon at uva.nl> - Noël Research Group - 2024
 Functions by Olly Bayley <o.m.bayley at uva.nl> - Noël Research Group - 2024
*/

#include <math.h>
#include <EEPROM.h>
#include "Device_id.h"	// Routines to read and write device id.

// --Constants--
// LCMS Trigger Pins
#define START_REQUEST_SIGNAL_PIN 2 // Pin to output to ERI Remote Pin #1 (White)
#define STOP_SIGNAL_PIN 3 // Pin to output to ERI Remote Pin #2 (Brown)
#define READY_SIGNAL_PIN 4 // Pin to output to ERI Remote Pin #3 (Green)

// Phase Sensor Read Pins
#define PHASE_SENSOR_OUT_A_PIN 6 // Pin to read phase sensor output (Orange)
#define PHASE_SENSOR_OUT_B_PIN 7 // Pin to read phase sensor output (Blue)
#define PHASE_SENSOR_CALIBRATE_PIN 8 // Pin to calibrate phase sensor (Green)

// Valve Control Pins
#define VALVE_A_IN_PIN 9  // Pin to to read valve position A (Vici Pin 3)
#define VALVE_B_IN_PIN 10 // Pin to to read valve position B (Vici Pin 4)
#define VALVE_A_OUT_PIN 11 // Pin to to set valve to position A (Vici Pin 5)
#define VALVE_B_OUT_PIN 12 // Pin to to set valve to position B (Vici Pin 6)

// Error codes (type)
#define ERROR_NO_ERROR 0	  // No error.
#define ERROR_SERIAL 1      // error value is variable number from error.
#define ERROR_PIN 2      	  // See pin.h

// EEPROM
#define EEPROM_ADDRESS_CHECK 0	// 1 byte char
#define DEFAULT_CHECK 42
#define EEPROM_ADDRESS_ID 1	// 20 bytes char[]
#define DEFAULT_ID "LCMS_Controller"

// --Global variables--
  // Error Handling
uint8_t error_type = 0;
uint8_t error_value = 0;
  //General
char good_acknowledge = 'k';
char bad_acknowledge = 'n';

//-----Action Methods-----
/**
 * Load stored values from EEPROM to system
 */
void load_defaults()
{
	uint8_t charvalue = 0;
	EEPROM.get(EEPROM_ADDRESS_CHECK, charvalue);
	if (charvalue == DEFAULT_CHECK)
	{
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
	eeprom_put_id(EEPROM_ADDRESS_ID);
}

/**
 * Reset stored values to original defaults
 */
void factory_reset()
{
	uint8_t charvalue = DEFAULT_CHECK;
	EEPROM.put(EEPROM_ADDRESS_CHECK, charvalue);
	init_id(DEFAULT_ID);
	eeprom_put_id(EEPROM_ADDRESS_ID);
}

/**
 * Reads the Switch valve position based on the A and B pin logic. Defaults to 'error' state on bad read.
 */
int read_valve_pos(){
  int valve_position = 2;  //Error
  if (digitalRead(VALVE_A_IN_PIN) == LOW && digitalRead(VALVE_B_IN_PIN) == HIGH){
    valve_position = 0;  //A
  }else if (digitalRead(VALVE_A_IN_PIN) == HIGH && digitalRead(VALVE_B_IN_PIN) == LOW){
    valve_position = 1;  //B
  }
  return valve_position;
}

/**
 * Reads the phase sensor output. Defaults to 'error' state on bad read.
 */
int read_phase_sensor(){
  uint8_t state = 3;  //Error
  uint8_t phase_sensor_a_pin = digitalRead(PHASE_SENSOR_OUT_A_PIN);
  uint8_t phase_sensor_b_pin = digitalRead(PHASE_SENSOR_OUT_B_PIN);
  if(phase_sensor_a_pin == HIGH && phase_sensor_b_pin == LOW){
    state = 0; //Clear Solution
  }else if(phase_sensor_a_pin == LOW && phase_sensor_b_pin == HIGH){
    state = 1; //Empty
  }else if(phase_sensor_a_pin == HIGH && phase_sensor_b_pin == HIGH){
    state = 2; //Absorbing Solution
  }
  return state;
}

/**
 * Sets switch valve position based input. Defaults to 'bad acknowledge' if input is not 1 or 0.
 */
char set_valve_pos(int variable_value_int){
  if (variable_value_int == 0){ //Set position to A
    digitalWrite(VALVE_A_OUT_PIN, LOW);
    digitalWrite(VALVE_B_OUT_PIN, HIGH);
    return good_acknowledge;
  }
  else if (variable_value_int == 1){ //Set position to B
    digitalWrite(VALVE_A_OUT_PIN, HIGH);
    digitalWrite(VALVE_B_OUT_PIN, LOW);
    return good_acknowledge;
  } else{
     return bad_acknowledge;
  }
}

/**
 * Sends 'START REQUEST' to LCMS
 */
void start_analysis(){
  digitalWrite(START_REQUEST_SIGNAL_PIN, LOW); // Set to LOW (0V)
  delay(100);
  digitalWrite(START_REQUEST_SIGNAL_PIN, HIGH); // Return to HIGH (5V)
}

/**
 * Sends 'STOP' to LCMS
 */
void stop_analysis(){
  digitalWrite(STOP_SIGNAL_PIN, LOW); // Set to LOW (0V)
  delay(100);
  digitalWrite(STOP_SIGNAL_PIN, HIGH); // Return to HIGH (5V)
}

/**
 * Sends calibrate signal to phase sensor. Code assumes the PS is calibrated to an empty line.
 */
void calibrate_ps(){
  digitalWrite(PHASE_SENSOR_CALIBRATE_PIN, LOW); // Set to LOW (0V)
  delay(100);
  digitalWrite(PHASE_SENSOR_CALIBRATE_PIN, HIGH); // Return to HIGH (5V)
}


//-----Command Interpreter-----
/**
 * Checks serial line for commands and executes them.
 */
void parse_serial(){
	while (Serial.available() > 0){
		char command = Serial.read();
		int variable_number = 0;
    int int_response = 3;  // Default response is error

		if (command == 'R' || command == 'r'){  // Comands to READ and return info to caller
			// Read variable
			variable_number = Serial.parseInt();
			switch (variable_number){
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
          // Valve position
          int_response = read_valve_pos();
					Serial.println(int_response);
					break;
        case 8:
          // LCMS ready state
          int_response = digitalRead(READY_SIGNAL_PIN);
          Serial.println(int_response);
        break;
        case 10:
          // Phase sensor state
          int_response = read_phase_sensor();
          Serial.println(int_response);
        break;
				default:
					// Syntax errors
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
		else if (command == 'S' || command == 's'){  // Comands to SEND 
			// Write variable
			variable_number = Serial.parseInt();
			Serial.read();
			int variable_value_int = 0;
			float variable_value_float = 0;
      int step = 0;
      char variable_char_acknowledge = "n";
			// Write device-wide variable
			switch (variable_number){
				case 1:
					// Device identifier
					serial_read_id();
          Serial.println(good_acknowledge);
					break;
				case 3:
					// Save defaults
					store_defaults();
          Serial.println(good_acknowledge);
					break;
				case 4:
					// Factory reset
					factory_reset();
          Serial.println(good_acknowledge);
					break;
        case 5:
					// Set valve position
          variable_value_int = Serial.parseInt();
          variable_char_acknowledge = set_valve_pos(variable_value_int);
          Serial.println(variable_char_acknowledge);
					break;
        case 6:
          // Send START REQUEST through START_REQUEST_SIGNAL_PIN
          start_analysis();
          Serial.println(good_acknowledge);
          break;
        case 7:
          // Send STOP through STOP_SIGNAL_PIN
          stop_analysis();
          Serial.println(good_acknowledge);
          break;
        case 9:
          // Send Calibrate
          calibrate_ps();
          Serial.println(good_acknowledge);
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
  pinMode(START_REQUEST_SIGNAL_PIN, OUTPUT);
  digitalWrite(START_REQUEST_SIGNAL_PIN, HIGH);  // Set to LCMS defaults on startup to prevent triggering upon conection init
  pinMode(STOP_SIGNAL_PIN, OUTPUT);
  digitalWrite(STOP_SIGNAL_PIN, HIGH);           // Set to LCMS defaults on startup to prevent triggering upon conection init
  pinMode(READY_SIGNAL_PIN, INPUT);
  digitalWrite(READY_SIGNAL_PIN, HIGH);           // Set to LCMS defaults on startup to prevent triggering upon conection init

  // Initialize Switch Pins
  pinMode(VALVE_A_OUT_PIN, OUTPUT);
  digitalWrite(VALVE_A_OUT_PIN, LOW);  // Set valve to Position A upon startup
  pinMode(VALVE_B_OUT_PIN, OUTPUT);
  digitalWrite(VALVE_B_OUT_PIN, HIGH); // Set valve to Position A upon startup
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
	}
}
