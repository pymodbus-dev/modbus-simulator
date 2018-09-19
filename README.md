# Modbus Simulator

Modbus Simulator with GUI based on modbus-tk and Pymodbus

## Checking Out the Source
    $ git clone https://github.com/riptideio/modbus-simulator.git
    $ cd modbus-simulator


## Development Instructions
1. create virtualenv and install requirements
   
    ```
    $ # Kivy depends on Cython, Install Cython before running the requirements
    $ pip install Cython==0.25.2
    $ pip install -r requirements
    $ # Choose Modbus Backend modbus_tk or pymodbus (default)
    $ # To install pymodbus
    $ pip install pymodbus==1.5.2
    $ # To install modbus tk
    $ Pip install modbus-tk

    ```


3. [Setup development environment](https://github.com/kivy/kivy/wiki/Setting-Up-Kivy-with-various-popular-IDE's)

## Running/Testing application

1. To run simulation with pymodbus backend, run `./tools/launcher`
2. To run sumulation with modbus-tk as backend run `./tools/launcher mtk`



A GUi should show up if all the requirements are met !!

![main_screen.png](/img/main_screen.png)

All the settings for various modbus related settings (block size/minimum/maximun values/logging) could be set and accessed from settings panel (use F1 or click on Settings icon at the bottom)
![settings_screen.png](img/settings_screen.png)

## Usage instructions
[![Demo Modbus Simulator](/img/simu.gif)](https://www.youtube.com/watch?v=a5-OridSlt8)

## Packaging for different OS (Standalone applications)
A standalone application specific to target OS can be created with Kivy package manager

1. [OSX](https://kivy.org/docs/guide/packaging-osx.html)
2. [Linux](http://bitstream.io/packaging-and-distributing-a-kivy-application-on-linux.html)
3. [Windows](http://kivy.org/docs/guide/packaging-windows.html)


# NOTE:
A cli version supporting both Modbus_RTU and Modbus_TCP is available here [modbus_simu_cli](https://github.com/dhoomakethu/modbus_sim_cli)
