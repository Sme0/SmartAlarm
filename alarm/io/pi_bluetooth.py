import serial
from time import sleep


'''
Only a single character gets sent over bluetooth:

> 0 (pi -> arduino) = confirmation request: allows response, switches on button's LED
> 1 (arduino -> pi) = confirmation message: sends response, switches off button's LED
> 2 (pi -> arduino) = end of confirmation window: disallows response, switches off button's LED

See end of file for sample code.
'''


class Bluetooth:
    def __init__(self):
        self.connection = serial.Serial("/dev/rfcomm0", 9600, timeout = 2)
        
    def process_incoming_message(self, message: str) -> str:
        return str(message).strip('b').strip(r"'").strip()
            
    def send_message(self, message) -> None:
        self.connection.write(message.encode())
        
    def listen(self, timeout: int) -> str:
        message = []
            
        for _ in range(timeout // 2):
            incoming = self.process_incoming_message(self.connection.read())
            if incoming == r"\r":
                return self.message_to_string(message)
            message.append(incoming)
        
        self.send_message("2")
            
            
    def message_to_string(self, message) -> str:
        string = ""
        if message != None:
            for i in message:
                string += i
            return string.strip()
                
                
                
class BluetoothConfirmation:
    def __init__(self, timeout: int, debug: bool = False) -> None:
        self.awaiting_confirmation = False
        self.received_confirmation = False
        self.received_message = ""
        
        self.bluetoothio = Bluetooth()
        self.reply_window = timeout
        
        self.debug = debug
        
        
    def await_confirmation(self) -> None:
        if self.debug:
            print("Awaiting confirmation...")
        
        self.received_message = self.bluetoothio.listen(self.reply_window)
        
        if self.received_message and "1" in self.received_message:
            self.received_confirmation = True
        
        else:
            self.received_confirmation = False
        
        
    def send_confirmation_request(self) -> None:
        self.received_confirmation = False
        self.bluetoothio.send_message("0")
        if self.debug:
            print("Sending confirmation request...")
        
    def check_confirmation(self) -> bool:
        if self.debug:
            if self.received_confirmation:
                print("\nThird-party confirmation received.")       
            else:
                print("Third-party confirmation not received.")
                
        return self.received_confirmation
        
    
# sample code
# see top comment for details about messages

if __name__ == "__main__":
    # initialise bluetooth confirmation class
    # 8 second wait time for a response, and enable console output
    connection = BluetoothConfirmation(8, True) 

    
    # send a confirmation request
    # this will switch on button's LED
    connection.send_confirmation_request()
    
    # listen for a response from the arduino (for number of seconds specified earlier)
    connection.await_confirmation()
    
    # check if a response has been received; if not then button's LED switches off
    # returns true if yes, false if no
    connection.check_confirmation()
            
            
            
            
        
