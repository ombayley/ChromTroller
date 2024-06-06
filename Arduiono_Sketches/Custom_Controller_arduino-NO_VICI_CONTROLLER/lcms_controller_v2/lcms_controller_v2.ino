/*
 Arduino UNO controller for Agilent LCMS

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
    5     | READ/WRITE  | FLOAT       | Number of ports in the switch valve.
    6     | READ/WRITE  | INT[0-1]    | Enable valve switching (1=enabled).
    7     | READ/WRITE  | INT[0-1]    | Valve position. Sends acknowledge signal when done. (0=Fill Sample Loop (A), 1=Inject Sample Loop (B)) 
    8     | COMMAND     | INT[1]      | Send  'START REQUEST' [ERI Remote Pin #1]. Active = Low.  Request to start injection cycle. Receiver is the autosampler.
    9     | COMMAND     | INT[1]      | Send  'STOP'          [ERI Remote Pin #2]. Active = Low.  Request to reach system ready state as soon as possible. Receiver is any module performing run-time controlled activities.
    10    | READ_ONLY   | INT[1]      | Read  'READY'         [ERI Remote Pin #3]. Active = high. Read system status to check if it is ready for next analysis.
  
 Error codes:
   type  |  description | value
   ------|--------------|--------------
   0     | No error     | Undefined
   1     | Serial error | Variable number which gave the issue
   2     | Other error  | TODO

 Hardware connections (Arduino UNO board):
   Agilent Infinity 1290 UPLC-MS
   Stepper Motor Driver + Vici Switch-Valve 

 Libraries:
   no external libraries.

  Math:
   A: NEMA stepper: 200 steps/revolution
   B: Motor driver: 8 microsteps

   Steps per Switch =  A/NUM_SWITCH_PORTS * B


 Template by Simone Pilon <s.pilon at uva.nl> - Noël Research Group - 2024
 Functions implemented by Olly Bayley <o.m.bayley at uva.nl> - Noël Research Group - 2024
*/

#include <math.h>
#include <EEPROM.h>
#include "Device_id.h"	// Routines to read and write device id.

// Pins 0 and 1 not used as they are also used to transmit serial data. 
// Pin 13 not used due to the inbuilt board LED (internal resistor can prevent the HIGH signal reaching 5V).

// LCMS Trigger Pins
#define START_REQUEST_SIGNAL_PIN 2 // Pin to output to ERI Remote Pin #1 (White)
#define STOP_SIGNAL_PIN 3 // Pin to output to ERI Remote Pin #2 (Brown)
#define READY_SIGNAL_PIN 4 // Pin to output to ERI Remote Pin #3 (Green)

// Valve Control Pins
#define PIN_EN 8 // Pin to enable stepper motor
#define PIN_DIR 9 // Pin to set direction of stepper motor
#define PIN_STEP 10 // Pin to set number of steps to take

// LED Pins
#define LED_A 11 // Pin to enable stepper motor
#define LED_B 12 // Pin to set direction of stepper motor

// Error codes (type)
#define ERROR_NO_ERROR 0	  // No error.
#define ERROR_SERIAL 1      // error value is variable number from error.
#define ERROR_PIN 2      	  // See pin.h

// EEPROM
#define EEPROM_ADDRESS_CHECK 0	// 1 byte char
#define DEFAULT_CHECK 42
#define EEPROM_ADDRESS_ID 1	// 20 bytes char[]
#define DEFAULT_ID "LCMS_Trigger"
#define EEPROM_ADDRESS_PORTS 21	// 1 byte int
#define DEFAULT_NUM_SWITCH_PORTS 6
#define EEPROM_ADDRESS_SPEED 22	// 4 byte int
#define DEFAULT_SWITCH_SPEED 200

// Global variables
uint8_t error_type = 0;
uint8_t error_value = 0;
uint8_t num_switch_ports = DEFAULT_NUM_SWITCH_PORTS;
uint8_t valve_position = 0;
bool valve_enabled = false;
float steps_per_rev = 200;
float microsteps = 8;
float StepsToSwitch = steps_per_rev / num_switch_ports * microsteps;
float switching_speed_delay = DEFAULT_SWITCH_SPEED;

/**
 * Load stored values from EEPROM to system
 */
void load_defaults()
{
	uint8_t charvalue = 0;
	EEPROM.get(EEPROM_ADDRESS_CHECK, charvalue);
	if (charvalue == DEFAULT_CHECK)
	{
    EEPROM.get(EEPROM_ADDRESS_SPEED, switching_speed_delay);
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
  EEPROM.put(EEPROM_ADDRESS_SPEED, switching_speed_delay);
  EEPROM.put(EEPROM_ADDRESS_PORTS, num_switch_ports);
	eeprom_put_id(EEPROM_ADDRESS_ID);
}

/**
 * Reset stored values to original defaults
 */
void factory_reset()
{
  switching_speed_delay = DEFAULT_SWITCH_SPEED;
  EEPROM.put(EEPROM_ADDRESS_SPEED, switching_speed_delay);
  num_switch_ports = DEFAULT_NUM_SWITCH_PORTS;
	EEPROM.put(EEPROM_ADDRESS_PORTS, num_switch_ports);
	uint8_t charvalue = DEFAULT_CHECK;
	EEPROM.put(EEPROM_ADDRESS_CHECK, charvalue);
	init_id(DEFAULT_ID);
	eeprom_put_id(EEPROM_ADDRESS_ID);
}

void set_led()
{
  if (valve_position ==1){
    digitalWrite(LED_A, LOW);
    digitalWrite(LED_B, HIGH);
  }
  if (valve_position ==0){
    digitalWrite(LED_A, HIGH);
    digitalWrite(LED_B, LOW);
  }
}

/**
 * Checks serial line for commands and executes them.
 */
void parse_serial()
{
	while (Serial.available() > 0)
	{
		char command = Serial.read();
		int variable_number = 0;

		if (command == 'R')  // Comands to READ and return info to caller
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
					// Device identifier
					Serial.println(num_switch_ports);
					break;
        case 6:
					// Device identifier
					Serial.println(valve_enabled);
					break;
        case 7:
					// Device identifier
					Serial.println(valve_position);
					break;
				default:
					// Syntax error
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
		else if (command == 'S')  // Comands to SEND 
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
					// Set number of ports in switch
          variable_value_float = Serial.parseFloat();
					num_switch_ports = variable_value_float;
					break;
        case 6:
					// Enable/Disable valve switching
          variable_value_int = Serial.parseInt();
					if (variable_value_int == 1){
          digitalWrite(PIN_EN, LOW); // Enable stepper motor
          valve_enabled = true;
          Serial.println("k (valve enabled)");
          }
          if (variable_value_int == 0){
          digitalWrite(PIN_EN, HIGH); // Disable stepper motor after movement
          valve_enabled = false;
          Serial.println("k (valve disabled)");
          }
					break;
        case 7:
					// Set valve position
          variable_value_int = Serial.parseInt();
          if (!valve_enabled){
            Serial.println("n (Valve not enabled)");
            break;
          }
					if (variable_value_int == valve_position){
            Serial.println("n (Valve already in position)");
            break;
          }
          if (variable_value_int == 1){
            digitalWrite(PIN_DIR, LOW); // Set direction
            for(step=0; step < StepsToSwitch; step++) {
                digitalWrite(PIN_STEP, HIGH);
                delayMicroseconds(switching_speed_delay); // Adjust delay to control speed
                digitalWrite(PIN_STEP, LOW);
                delayMicroseconds(switching_speed_delay); // Adjust delay to control speed
            }
            Serial.println("Steps Moved: ");
            Serial.println(StepsToSwitch);
            valve_position = variable_value_int;
            set_led();
            Serial.println("k");
          }
          if (variable_value_int == 0){
            digitalWrite(PIN_DIR, HIGH); // Set direction
            for(step=0; step < StepsToSwitch; step++) {
                digitalWrite(PIN_STEP, HIGH);
                delayMicroseconds(switching_speed_delay); // Adjust delay to control speed
                digitalWrite(PIN_STEP, LOW);
                delayMicroseconds(switching_speed_delay); // Adjust delay to control speed
            }
            Serial.println("Steps Moved: ");
            Serial.println(StepsToSwitch);
            valve_position = variable_value_int;
            set_led();
            Serial.println("k");
          }
					break;
        case 8:
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
        case 9:
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

// This is run once when the Arduino is powered up.
void setup()
{
	// Load stored values from EEPROM
	load_defaults();
	
	// Initialize LCMS Trigger Pins
  digitalWrite(START_REQUEST_SIGNAL_PIN, HIGH);
	pinMode(START_REQUEST_SIGNAL_PIN, OUTPUT);
  digitalWrite(STOP_SIGNAL_PIN, HIGH);
  pinMode(STOP_SIGNAL_PIN, OUTPUT);
  digitalWrite(READY_SIGNAL_PIN, LOW);
  pinMode(READY_SIGNAL_PIN, INPUT);

  // Initialize Stepper Motor Pins
  pinMode(PIN_EN, OUTPUT);
  pinMode(PIN_DIR, OUTPUT);
  pinMode(PIN_STEP, OUTPUT);

  // Initialize LED Pins
  pinMode(LED_A, OUTPUT);
  pinMode(LED_B, OUTPUT);

	// Initialize Serial interface
	Serial.begin(9600);

  // Make sure the correct LED is on
  set_led();
}

// This is run in a loop constantly during execution.
void loop()
{
	while (true)
	{
		parse_serial();
	}
}
