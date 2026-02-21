# Embedded-Systems
Emerging systems architectures and technologies.

# Smart Thermostat

<img width="100%" height="100%" alt="Smarth Thermostat" src="https://github.com/user-attachments/assets/5bf4c3da-cbba-4e3e-bd95-b59af73cc9f8" />

## Summarize the project and what problem it was solving.
#### This project implements a smart thermostat system using a Raspberry Pi, designed to create an intuitive and multi-functional temperature control system with clear user feedback. The thermostat operates using three main states (Off, Heat, and Cool) managed through a state machine architecture, while continuously monitoring temperature data from an AHT20 sensor.

The system addresses several practical challenges:

• User interface clarity: Multiple output devices, including an LCD screen, seven-segment display, and LED indicators, provide redundant feedback so the user can easily understand the current system status at all times.

• International usability: Support for both Fahrenheit and Celsius allows temperature scale conversion without requiring different hardware setups for different regions.

• Remote monitoring: Serial communication enables temperature data logging and allows the system to be monitored remotely through a centralized server.

• Responsive operation: Threaded display management keeps the interface responsive while temperature readings and hardware control processes run continuously in the background.

## What did you do particularly well?
#### State Machine Architecture
I implemented the thermostat control logic using Python’s statemachine library, which allowed me to clearly separate each operational state and its transitions. Each state includes defined entry and exit behaviors, making the system easier to understand, test, and debug. The transition flow (Off → Heat → Cool → Off) is implemented as a simple and readable cycle, keeping the overall control logic clean and maintainable.

#### Multi-Modal User Feedback
One of the strongest parts of this project is the use of multiple feedback methods for the user interface. The seven-segment display provides quick visual confirmation of actions (H, C, O, u, d), while the LCD shows more detailed system information. LED behavior also communicates system status effectively, using pulsing versus solid light patterns to indicate whether the thermostat is actively working toward the setpoint or has already reached it. This layered feedback helps ensure the system state is clear regardless of how the user interacts with it.

#### Code Documentation and Organization
The code is organized with clear sections and consistent documentation throughout. I used descriptive headers and comments to explain the purpose of each component and hardware interaction. Helper functions are grouped logically based on functionality, such as seven-segment display control and cleanup routines, and the program structure follows a top-down flow from hardware setup to state machine definition and finally the main execution loop.

#### Temperature Scale Conversion
The temperature scale toggle demonstrates intentional user experience design. A short button press handles normal state changes, while a long press activates Fahrenheit/Celsius conversion without adding extra controls. When the scale changes, the setpoint is automatically recalculated so the thermal threshold remains consistent. Visual confirmation through the blinking C or F indicator with a decimal point provides clear feedback that the conversion was successful.

## Where could you improve?
#### Error Handling and Robustness
Although cleanup routines include try-except handling, runtime error management could be improved. The LCD initialization already includes a fallback if the device is not detected, but failures during normal operation, such as sensor read errors or I2C communication issues, are not explicitly handled. Adding try-except blocks around temperature reads and introducing retry logic would make the system more robust against temporary hardware or communication failures.

#### Configuration Management
Several system parameters are currently hardcoded, including GPIO pin assignments (17, 18, 23, 24, 25, 27, 22), the I2C address (0x27), timing intervals (30-second serial updates and 3-second segment timeout), and the default 72°F setpoint. Moving these values into a centralized configuration section or external JSON configuration file would improve maintainability and make the thermostat easier to adapt to different hardware configurations without modifying core logic.

#### Data Persistence
At the moment, the thermostat resets its state and setpoint after power loss or reboot. Implementing persistence by saving the current state, temperature scale, and setpoint to a file during shutdown and restoring them on startup would improve usability. Storing periodic temperature readings in a CSV log could also allow for historical analysis and long-term trend monitoring.

#### Expanded Seven-Segment Display Usage
Another improvement would be expanding the information shown on the seven-segment display. Currently it mainly provides status indicators, but it could also display numerical values such as the current temperature or setpoint by showing digits sequentially (for example, 72 displayed as 7 followed by 2). Providing more detailed numeric feedback would reduce dependence on the LCD and potentially allow the thermostat to operate fully even without the LCD connected.

## What tools and/or resources are you adding to your support network?
#### Answer
## What skills from this project will be particularly transferable to other projects and/or course work?
#### Answer
## How did you make this project maintainable, readable, and adaptable?
#### Answer
