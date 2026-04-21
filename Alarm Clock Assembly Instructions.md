# Smart Alarm Assembly

## Component List
- Raspberry Pi + Grove Pi Plus module
- Joystick
- Buzzer
- LCD display
- LED button x2
- Arduino + Grove module
- Serial bluetooth module

---

## Pi assembly
1. Attach the Grove Pi module to the top of the Raspberry Pi

2. Connect the LCD display to the I2C-1 port on the Grove Pi.

3. Connect the joystick to the A0 port on the Grove Pi

4. Connect the buzzer to the D5 port on the Grove Pi

5. Connect the button to the D3 port on the Grove Pi

6. (Optional) connect the HDMI cable to the Pi and a monitor

7. Connect the power cable to the Pi and a socket

---

## Arduino assembly
1. Connect the Grove module to the top of the Arduino

2. Connect the bluetooth serial module to the D8 port on the Grove module

3. Connect the LED button to the D3 port on the Grove module

4. Connect the Arduino to a laptop or other power source via the usb cable

---

## Bluetooth connection
1. Open a new terminal window on the Pi

2. Ensuring the arduino is on and running, run:  
  `sudo rfcomm connect hci0 00:0E:EA:CF:6D:A5`  

3. If a connection is successful, minimise the terminal window

4. If a connection is unable to be made, run the following commands:  
`bluetoothctl`  
`remove 00:0E:EA:CF:6D:A5`  
`scan on`  
[wait for 00:0E:EA:CF:6D:A5 to show up]  
`scan off`  
`pair 00:0E:EA:CF:6D:A5`  
[pin]: `1234`  
`trust 00:0E:EA:CF:6D:A5`  
`quit`  
`sudo rfcomm connect hci0 00:0E:EA:CF:6D:A5`
