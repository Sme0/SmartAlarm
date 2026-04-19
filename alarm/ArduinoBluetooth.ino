#include <SoftwareSerial.h>

#define RxD 8    // Arduino RX pin for Bluetooth
#define TxD 9    // Arduino TX pin for Bluetooth
#define PIR_MOTION_SENSOR 2  // PIR sensor input pin

SoftwareSerial blueToothSerial(RxD, TxD);
char incoming;

const int ledPin = 3;     // the number of the LED pin
const int buttonPin = 4;  // the number of the pushbutton pin

int buttonState;          // the state of the button (HIGH or LOW)
int ledState = LOW;       // the current state of the LED (HIGH or LOW)

bool awaitingResponse = false;


void setup()
{
  pinMode(buttonPin, INPUT);
  pinMode(ledPin, OUTPUT);
  digitalWrite(ledPin, ledState);
  

  // 4. Start the hardware Serial for debugging and messages to the Serial Monitor.
  Serial.begin(9600);

  while(!Serial) { ; }
  Serial.println("Started");

  pinMode(PIR_MOTION_SENSOR, INPUT);
  pinMode(RxD, INPUT);
  pinMode(TxD, OUTPUT);

  setupBlueToothConnection();

  Serial.flush();
  blueToothSerial.flush();
}

void loop()
{
  // check for incoming bluetooth signals
  if (blueToothSerial.available() > 0) {
    incoming = blueToothSerial.read();

    // 0 = confirmation request
    if (incoming == '0') {
      awaitingResponse = true;
      ledState = HIGH;
      digitalWrite(ledPin, ledState);
    }

    // 2 = confirmation expired
    else if (incoming == '2') {
      awaitingResponse = false;
      ledState = LOW;
      digitalWrite(ledPin, ledState);
    }
    
  }

  buttonState = digitalRead(buttonPin);

  // if button pressed and awaiting response then send response (1)
  if (buttonState == 0 && awaitingResponse == true) {
        blueToothSerial.println("1");
        awaitingResponse = false;
        ledState = LOW;
        digitalWrite(ledPin, ledState);
    }

  delay(50);
}

/***************************************************************************
* Function Name: setupBlueToothConnection
* Description:   Initializes the Bluetooth connection with AT commands.
*                Configures the baud rate, role, name, and authentication.
***************************************************************************/
void setupBlueToothConnection()
{
  // 10. Begin a software serial session at 9600 baud for the Bluetooth module.
  blueToothSerial.begin(9600);

  // 11. Send a series of AT commands to configure the BLE module.
  blueToothSerial.print("AT");
  delay(200);

  // Set the module’s baud rate to 9600 (AT+BAUD4 typically means 9600).
  blueToothSerial.print("AT+BAUD4");
  delay(200);

  // Set the module’s role to “S” (often means slave/peripheral).
  blueToothSerial.print("AT+ROLES");
  delay(200);

  // Assign a name (up to 12 characters). Here, it’s “Slave”.
  blueToothSerial.print("AT+NAMEAlarmSlave");
  delay(200);

  // Enable authentication (AT+AUTH1).
  blueToothSerial.print("AT+AUTH1");
  delay(200);

  // 12. Flush any residual data from the software serial buffer.
  blueToothSerial.flush();
  Serial.println("Finished Bluetooth Setup");
}