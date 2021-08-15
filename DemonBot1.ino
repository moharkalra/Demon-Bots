//TMP36 Pin Variables
#include <Servo.h>
int sensorPin = 4; //the analog pin the TMP36's Vout (sense) pin is connected to
                        //the resolution is 10 mV / degree centigrade with a
                        //500 mV offset to allow for negative temperatures
Servo slapperServo;
Servo locketServo; 
int slapper = 6;
int locket = 5;

bool flag = false;
int lastTemp = 27.0;
int lastChange = 0.0;
/*
 * setup() - this function runs once when you turn your Arduino on
 * We initialize the serial connection with the computer
 */
void setup()
{

locketServo.attach(locket);
locketServo.write(70);
delay(1000);

locketServo.detach();
  int reading = analogRead(sensorPin);  
 Serial.begin(9600);
 // converting that reading to voltage, for 3.3v arduino use 3.3
 int voltage = reading * 5.0;



 
 // now print out the temperature
  lastTemp = (voltage - 512);
//  Serial.println(lastTemp);
//  Serial.println("----");
}
 
void loop()                     // run over and over again
{
 //getting the voltage reading from the temperature sensor
 int reading = analogRead(sensorPin);  
 
 // converting that reading to voltage, for 3.3v arduino use 3.3
 int voltage = reading * 5.0;


 

 
 // now print out the temperature
int temperatureC = (voltage - 512) ;  //converting from 10 mv per degree wit 500 mV offset
 int change = -(lastTemp-temperatureC);
// Serial.println(temperatureC);
// Serial.println(change);

 if(flag ==true){
  if(change<=-10 && lastChange<=-10){
    turnOff();
  }
 }
 else{
  if(change>=10){
    turnOn();
  }
 }

 lastChange = change;
 lastTemp = temperatureC;
//  Serial.println(lastTemp);
//  Serial.println(lastChange);
//  Serial.println("----");
 digitalWrite(1, HIGH);
 delay(2000);                                     //waiting a second
}

void turnOn(){
  flag = true;
  locketServo.attach(locket);
  locketServo.write(5);
  delay(1000);
  locketServo.detach();
  slapperServo.attach(slapper);
  slapperServo.write(135);
}
void turnOff(){
  flag = false;
  locketServo.attach(locket);
  locketServo.write(70);
   delay(500);
  locketServo.detach();
  
  slapperServo.write(0);
   delay(500);
  slapperServo.detach();
}
