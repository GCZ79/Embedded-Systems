#!/usr/bin/env python3
#--------------------------------------------------------------------------
# CS 350 - Final Project
# Author: GCZ79
# Date: 02/19/2026
# Description: Thermostat with states Off, Heat, and Cool (O, H, C)
#              with temperature scale toggle (F/C) and 7-segment display
# Peripherals: 2 LEDs representing its state (Red = H, Blu = C)
#              1 Button to cycle through the three states, long press toggles
#                temperature scale between Fahrenheit (F.) and Celsius (C.)
#              2 Buttons to adjust the setPoint up (u) or down (d)
#              1 LCD display to show date/time and temperature/state info
#              1 Seven-segment display for user feedback on values changes
#              1 Temperature/Humidity sensor AHT20
#              1 UART serial connection to send a status update to the
#                TemperatureServer over the serial port every 30 seconds
#--------------------------------------------------------------------------

##---------##
## Imports ##
##---------##
from time import sleep                            # sleep/delay executio
from datetime import datetime                     # date/time for LCD/logs
from statemachine import StateMachine, State      # StateMachine base class
import board                                      # I2C bus 
import adafruit_ahtx0                             # Temperature/Humidity sensor 
from RPLCD.i2c import CharLCD                     # I2C LCD library    
import serial                                     # Serial port f
from gpiozero import Button, PWMLED, OutputDevice # GPIO for buttons and LEDs
from threading import Thread                      # Create separate Thread 
from math import floor                            # Temperature calculations

##------------##
## DEBUG flag ## Boolean value to indicate whether or not to print logs on console
##------------##

DEBUG = True

##-------------------##
## 7-segment Display ## Configuration and helper functions
##-------------------##

# Constants to indicate bit order when sending data
LSBFIRST = 1 # Least Significant Bit First
MSBFIRST = 2 # Most Significant Bit First

# Hex codes for digits 0-9 and letters A-F, H, d, u
num = [0xc0, 0xf9, 0xa4, 0xb0, 0x99,       # 0-4 (indexes=0-4)
       0x92, 0x82, 0xf8, 0x80, 0x90,       # 5-9 (indexes=5-9)
       0x88, 0x83, 0xc6, 0xa1, 0x86, 0x8e, # A-F (indexes=10-15)
       0x89, 0xA1, 0xE3                    # H, d, u (indexes=16-18)
       ]

# 74HC595 shift register pins
dataPin = OutputDevice(17)  # DS (Pin 14)
latchPin = OutputDevice(27) # ST_CP (Pin 12)
clockPin = OutputDevice(22) # CH_CP (Pin 11)

##
## Helper function to send serial data to the 74HC595 shift register
## 'order' determines bit order: LSBFIRST or MSBFIRST
##
def shiftOut(order, val):
    """Send serial data to the 74HC595 shift register"""
    for i in range(0, 8):
        clockPin.off()
        if order == LSBFIRST:
            dataPin.on() if (0x01 & (val >> i) == 0x01) else dataPin.off()
        elif order == MSBFIRST:
            dataPin.on() if (0x80 & (val << i) == 0x80) else dataPin.off()
        clockPin.on()

##
## Helper function to display digit on seven-segment display
## Uses the global 'num' array for segment bit patterns
##
def display_segment(digit):
    """Display a digit (0-18) on the seven-segment display"""
    if 0 <= digit < len(num):
        latchPin.off()                 # Prepare shift register
        shiftOut(MSBFIRST, num[digit]) # Send data
        latchPin.on()                  # Update output

##
## Helper function to turn off seven-segment display
##
def clear_segment():
    """Turn off all segments on the seven-segment display"""
    try:
        latchPin.off()
        shiftOut(MSBFIRST, 0xFF) # 0xFF turns off all segments
        latchPin.on()
    except Exception as e:
        if DEBUG:
            print(f"Error clearing segment: {e}")

##
## Helper function to blink a character
## blinks: number of blinks - duration: time each blink lasts
##
def blink_segment(character, blinks=5, blink_duration=0.3):
    """Blink a character on the seven-segment display"""
    if character.upper() == 'C':
        digits = num[12] & 0x7F    # C + dot (Celsius)
    elif character.upper() == 'F':
        digits = num[15] & 0x7F    # F + dot (Fahrenheit)
    else:
        return

    for _ in range(blinks):
        latchPin.off()
        shiftOut(MSBFIRST, digits)
        latchPin.on()
        sleep(blink_duration)
        clear_segment()
        sleep(blink_duration)

##
## Helper function to create an animation (rotate segments)
## uses segments a > b > c > d > e > f > a > repeat
## rotations: number of full circles - delay: speed of animation
##
def rotate_segments(rotations=4, delay=0.06):
    """Create circular motion on the 7-segment display"""
    sequence = [
        0b11111110,  # a
        0b11111101,  # b
        0b11111011,  # c
        0b11110111,  # d
        0b11101111,  # e
        0b11011111,  # f
        0b11111110   # a
    ]

    for _ in range(rotations):
        for pattern in sequence:
            latchPin.off()
            shiftOut(MSBFIRST, pattern)
            latchPin.on()
            sleep(delay)

    clear_segment()

##-----##
## I2C ## Temperature/Humidity sensor configuration
##-----##
i2c = board.I2C() # Create I2C instance to communicate with devices on I2C bus
thSensor = adafruit_ahtx0.AHTx0(i2c) # Initialize Temperature/Humidity sensor

##--------##
## Serial ## UART configuration
##--------##
ser = serial.Serial(
        port='/dev/ttyS0', # This would be /dev/ttyAM0 prior to Raspberry Pi 3
        baudrate = 115200, # This sets the speed of the serial interface in
                           # bits/second
        parity=serial.PARITY_NONE,      # Disable parity
        stopbits=serial.STOPBITS_ONE,   # Serial protocol will use one stop bit
        bytesize=serial.EIGHTBITS,      # We are using 8-bit bytes 
        timeout=1          # Configure a 1-second timeout
)

##------##
## LEDs ## GPIO pin configuration
##------##
redLight = PWMLED(18)
blueLight = PWMLED(23)

##-------------------##
## LCD display (I2C) ## Configuration
##-------------------##
lcd = None
try:
    lcd = CharLCD('PCF8574', 0x27, cols=16, rows=2)
    print("I2C LCD initialized at address 0x27")
except Exception as e:
    print(f"LCD not available: {e}")
    print("Check I2C connection. Run 'i2cdetect -y 1' to find address")
    lcd = None

##
## cleanupDisplay - Method used to cleanup the LCD display
##
def cleanupDisplay():
    """Clean up LCD display resources"""
    if lcd:
        try:
            lcd.clear()
            lcd.backlight_enabled = False
        except:
            pass

##-----------------------------------##
## Cleanup function for all hardware ##
##-----------------------------------##
def cleanupAll():
    """Clean up all GPIO resources"""
    print("\nCleaning up GPIO and shutting down...")

    # Clear seven-segment display
    try:
        clear_segment()
        sleep(0.2)
    except:
        pass

    # Turn off both LEDs
    try:
        redLight.off()
        blueLight.off()
        sleep(0.1)
    except:
        pass

    # Cleanup LCD
    try:
        cleanupDisplay()
    except:
        pass

    # Close 7-segment GPIO pins
    try:
        dataPin.close()
        latchPin.close()
        clockPin.close()
    except:
        pass

    # Close buttons
    try:
        greenButton.close()
    except:
        pass

    try:
        redButton.close()
    except:
        pass

    try:
        blueButton.close()
    except:
        pass

    print("Cleanup complete.\n")

##
## TemperatureMachine - This is our StateMachine implementation class.
## The purpose of this state machine is to manage the three states
## handled by our thermostat:
##
##  off
##  heat
##  cool
##
##
class TemperatureMachine(StateMachine):
    "A state machine designed to manage our thermostat"

    ##
    ## Define the three states for our machine.
    ##
    ##  off - nothing lit up
    ##  red - only red LED fading in and out
    ##  blue - only blue LED fading in and out
    ##
    off = State(initial = True)
    heat = State()
    cool = State()

    ##
    ## Default temperature setPoint is 72 degrees Fahrenheit
    ##
    setPoint = 72

    ##
    ## Temperature scale tracking
    ## Default to Fahrenheit for thermostat operation
    ##
    tempScale = 'F'  # 'F' for Fahrenheit, 'C' for Celsius

    ##
    ## cycle - event that provides the state machine behavior
    ## of transitioning between the three states of our 
    ## thermostat
    ##
    cycle = (
        off.to(heat) |
        heat.to(cool) |
        cool.to(off)
    )

    ##
    ## on_enter_heat - Action performed when the state machine transitions
    ## into the 'heat' state
    ##
    def on_enter_heat(self):
        self.updateLights()                       # Update LEDs based on temp
        display_segment(16)                       # Show 'H' on the 7-segment display
        self.last_segment_update = datetime.now() # Track last display update

        if(DEBUG):
            print("* Changing state to heat")

    ##
    ## on_exit_heat - Action performed when the statemachine transitions
    ## out of the 'heat' state.
    ##
    def on_exit_heat(self):
        redLight.off()

    ##
    ## on_enter_cool - Action performed when the state machine transitions
    ## into the 'cool' state
    ##
    def on_enter_cool(self):
        self.updateLights()
        display_segment(12)                       # Show 'C' on the 7-segment display
        self.last_segment_update = datetime.now()

        if(DEBUG):
            print("* Changing state to cool")

    ##
    ## on_exit_cool - Action performed when the statemachine transitions
    ## out of the 'cool' state.
    ##
    def on_exit_cool(self):
        blueLight.off()

    ##
    ## on_enter_off - Action performed when the state machine transitions
    ## into the 'off' state
    ##
    def on_enter_off(self):
        redLight.off()
        blueLight.off()
        display_segment(0)                        # Show 'O' on the 7-segment display
        self.last_segment_update = datetime.now()

        if(DEBUG):
            print("* Changing state to off")

    ##
    ## processTempStateButton - Utility method used to send events to the 
    ## state machine. This is triggered by the button_pressed event
    ## handler for our first button
    ##
    def processTempStateButton(self):
        if(DEBUG):
            print("Cycling Temperature State")

        self.cycle()

    ##
    ## processTempIncButton - Utility method used to update the 
    ## setPoint for the temperature. This will increase the setPoint
    ## by a single degree. This is triggered by the button_pressed event
    ## handler for our second button
    ##
    def processTempIncButton(self):
        if(DEBUG):
            print("Increasing Set Point")

        self.setPoint += 1
        self.updateLights()

        display_segment(18) # Show 'u' for the red button (up)
        self.last_segment_update = datetime.now()

    ##
    ## processTempDecButton - Utility method used to update the 
    ## setPoint for the temperature. This will decrease the setPoint
    ## by a single degree. This is triggered by the button_pressed event
    ## handler for our third button
    ##
    def processTempDecButton(self):
        if(DEBUG):
            print("Decreasing Set Point")

        self.setPoint -= 1
        self.updateLights()
        
        display_segment(17) # Show 'd' for the blue button (down)
        self.last_segment_update = datetime.now()

    ##
    ## processScaleButton - Utility method to toggle between Fahrenheit 
    ## and Celsius. This is triggered by a long press on the green button.
    ## When scale changes, blinks the appropriate letter on 7-segment display
    ##
    def processScaleButton(self):
        if(DEBUG):
            print("Toggling Temperature Scale")
        
        # Toggle the scale
        if self.tempScale == 'F':
            self.tempScale = 'C'
            if(DEBUG):
                print("*** Changing to Celsius")
            blink_segment('C', blinks=5, blink_duration=0.3)
            self.setPoint = int((self.setPoint - 32) * 5 / 9)
        else:
            self.tempScale = 'F'
            if(DEBUG):
                print("*** Changing to Fahrenheit")
            blink_segment('F', blinks=5, blink_duration=0.3)
            self.setPoint = int((self.setPoint * 9 / 5) + 32)

        # Restore display to previous state
        self.restore_segment_display()

    ##
    ## Helper function to restore 7-segment display after an interruction
    ##
    def restore_segment_display(self):
        """Restore the 7-segment symbol based on current thermostat state"""
        if self.current_state == self.heat:
            display_segment(16)   # H
        elif self.current_state == self.cool:
            display_segment(12)   # C
        elif self.current_state == self.off:
            display_segment(0)    # O

        self.last_segment_update = datetime.now()

    ##
    ## check_segment_timeout - Clear 7-segment display after "segment_timeout" seconds
    ##
    last_segment_update = None
    segment_timeout = 3  # seconds

    def check_segment_timeout(self):
        if self.last_segment_update is not None:
            elapsed = (datetime.now() - self.last_segment_update).total_seconds()
            if elapsed >= self.segment_timeout:
                clear_segment()
                self.last_segment_update = None

    ##
    ## updateLights - Utility method to update the LED indicators on the 
    ## Thermostat
    ##
    def updateLights(self):
        ## Get temperature in the current scale
        if self.tempScale == 'F':
            temp = floor(self.getFahrenheit())
        else:
            temp = floor(self.getCelsius())
            
        redLight.off()
        blueLight.off()
    
        ## Verify values for debug purposes
        if(DEBUG):
            print(f"State: {self.current_state.id}")
            print(f"SetPoint: {self.setPoint} {self.tempScale}")
            print(f"Temp: {temp} {self.tempScale}")

        # Determine visual identifiers
        if self.current_state.id == 'heat':
            if temp < self.setPoint:
                # Temperature below setpoint - fade red LED
                redLight.pulse()
            else:
                # Temperature at or above setpoint - solid red LED
                redLight.on()
        elif self.current_state.id == 'cool':
            if temp > self.setPoint:
                # Temperature above setpoint - fade blue LED
                blueLight.pulse()
            else:
                # Temperature at or below setpoint - solid blue LED
                blueLight.on()
        # If state is 'off', both lights remain off (already turned off above)

    ##
    ## run - kickoff the display management functionality of the thermostat
    ##
    def run(self):
        myThread = Thread(target=self.manageMyDisplay)
        myThread.start()

    ##
    ## Get the temperature in Fahrenheit
    ##
    def getFahrenheit(self):
        t = thSensor.temperature
        return (((9/5) * t) + 32)

    ##
    ## Get the temperature in Celsius
    ##
    def getCelsius(self):
        return thSensor.temperature

    ##
    ##  Configure output string for the Thermostat Server
    ##  Always outputs in Fahrenheit for consistency with server
    ##
    def setupSerialOutput(self):
        tempF = self.getFahrenheit()
        state = self.current_state.id
        setpointF = self.setPoint if self.tempScale == 'F' else int((self.setPoint * 9 / 5) + 32)
        output = f"{state},{tempF:.1f},{setpointF}"

        return output

    ## Continue display output
    endDisplay = False

    ##
    ##  This function is designed to manage the LCD Display
    ##
    def manageMyDisplay(self):
        counter = 1
        altCounter = 1
        while not self.endDisplay:
            ## Only display if the DEBUG flag is set
            if(DEBUG):
                print("Processing Display Info...")

            ## Grab the current time        
            current_time = datetime.now()

            ## Setup display line 1
            lcd_line_1 = current_time.strftime('%b %d  %H:%M:%S\n')

            ## Setup Display Line 2
            if(altCounter < 6):
                # Display current temperature in current scale
                if self.tempScale == 'F':
                    temp = self.getFahrenheit()
                    lcd_line_2 = f"Temp: {temp:.1f} F"
                else:
                    temp = self.getCelsius()
                    lcd_line_2 = f"Temp: {temp:.1f} C"

                altCounter = altCounter + 1
            else:
                # Display state and setpoint in current scale
                state = self.current_state.id.upper()
                lcd_line_2 = f"{state} SP: {self.setPoint} {self.tempScale}"

                altCounter = altCounter + 1
                if(altCounter >= 11):
                    # Run the routine to update the lights every 10 seconds
                    # to keep operations smooth
                    self.updateLights()
                    altCounter = 1

            ## Update Display (using I2C LCD)
            if lcd:
                lcd.clear()
                lcd.write_string(lcd_line_1)
                lcd.cursor_pos = (1, 0)  # Move to line 2
                lcd.write_string(lcd_line_2)

            ## Update server every 30 seconds
            if(DEBUG):
               print(f"Counter: {counter}")
            if((counter % 30) == 0):
                # Show activity animation while sending data
                rotate_segments(rotations=4, delay=0.05)
                # Restore display to previous state
                self.restore_segment_display()
                # Send data to server
                ser.write(self.setupSerialOutput().encode())

                counter = 1
            else:
                counter = counter + 1
            
            self.check_segment_timeout()
            sleep(1)

        ## Cleanup display
        cleanupDisplay()

    ## End class TemperatureMachine definition

##
## Setup our State Machine
##
tsm = TemperatureMachine()
tsm.run()

##
## Configure our green button to use GPIO 24 and to execute
## the method to cycle the thermostat when pressed (short press)
## and toggle scale when held (long press)
##
greenButton = Button(24, hold_time=2)

# Global flag
green_long_pressed = False

def handle_green_release():
    global green_long_pressed
    if green_long_pressed:
        # Long press already handled, reset flag and skip short press
        green_long_pressed = False
        return
    # Short press logic
    tsm.processTempStateButton()

def handle_green_hold():
    global green_long_pressed
    green_long_pressed = True
    tsm.processScaleButton()

greenButton.when_released = handle_green_release
greenButton.when_held = handle_green_hold

##
## Configure our Red button to use GPIO 16 and to execute
## the function to increase the setpoint by a degree.
##
redButton = Button(16)
redButton.when_pressed = tsm.processTempIncButton

##
## Configure our Blue button to use GPIO 25 and to execute
## the function to decrease the setpoint by a degree.
##
blueButton = Button(25)
blueButton.when_pressed = tsm.processTempDecButton

##
## Setup loop variable
##
repeat = True

##
## Display startup message
##
if DEBUG:
    print("\n" + "="*60)
    print("Thermostat with Temperature Scale Control")
    print("="*60)
    print("Green Button (GPIO 24):")
    print(" - Short press: Cycle thermostat state (Off/Heat/Cool)")
    print(" - HOLD (2 sec): Toggle F/C scale (with 7-segment blink)")
    print("Red Button (GPIO 16):  Adjust setpoint Up")
    print("Blue Button (GPIO 25): Adjust setpoint Down")
    print("="*60)
    print("I2C LCD: Shows date/time and temp/state info")
    print("7-Segment Display: Blinks 'C' or 'F' when scale changes")
    print("Press Ctrl+C to exit")
    print("="*60 + "\n")

##
## Repeat until the user creates a keyboard interrupt (CTRL-C)
##
while repeat:
    try:
        ## wait
        sleep(30)

    except KeyboardInterrupt:
        ## Catch the keyboard interrupt (CTRL-C) and exit cleanly
        print("Exiting...")

        ## Stop the loop
        repeat = False
        
        ## Close down the display thread
        tsm.endDisplay = True
        sleep(1)
        
        ## Clean up all hardware
        cleanupAll()