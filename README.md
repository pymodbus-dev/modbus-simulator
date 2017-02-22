# Modbus Simulator

Modbus Simulator with GUI based on modbus-tk

## Requirements
* [modbus-tk](https://pypi.python.org/pypi/modbus_tk)
* [kivy 1.9.0 >](http://kivy.org/#download)

## Checking Out the Source
    $ git clone https://bitbucket.org/sanjaykv/modbus-simulator
    $ cd modbus_simulator

## Development Instructions
1. install kivy
    - [OSx](https://kivy.org/docs/installation/installation-osx.html)
    - [Linux](http://kivy.org/docs/installation/installation-linux.html#ubuntu-11-10-or-newer)
    - [Windows](http://kivy.org/docs/installation/installation-windows.html)

2. install modbus-tk
    * On Mac kivy uses its own virtual env ,hence all required modules needs to be installed seperatly [installing modules](http://kivy.org/docs/installation/installation-macosx.html#installing-modules)
        - kivy -m pip install modbus-tk
3. [Setup development environment](https://github.com/kivy/kivy/wiki/Setting-Up-Kivy-with-various-popular-IDE's)

## Running/Testing application
    $ cd modbus_simulator
    $ kivy main.py
A GUi should show up if all the requirements are met !!

![Screen Shot 2015-11-01 at 7.25.50 PM.png](https://bitbucket.org/repo/X9byrq/images/4179375251-Screen%20Shot%202015-11-01%20at%207.25.50%20PM.png)

## Usage instructions
1. Select the interface (only TCP supported as of now)
2. Enter the desired PORT 
3. Start Simulation
4. Add Slave
    * to add a single slave just click on 'add' 
    * one can play around with values in 'from'/'to'/'count' text fields to add multiple slaves 
    * to delete a selected slave use "delete' button
    * 'enable all' button is not implemented yet
5. Add Data blocks
    * select a slave to enable Datablock tab pane
    * use button 'add' in Datablock pane to add data (0 based offset)
    * to delete a datablock ,select an item and use 'delete' button in Datablock pane
6. To simulate data , press 'Simulate' button
7. All the settings for various modbus related settings (block size/minimum/maximun values/logging) could be set and accessed from settings panel (use F1 or click on Settings icon at the bottom)
![Screen Shot 2015-11-01 at 8.20.07 PM.png](https://bitbucket.org/repo/X9byrq/images/2785617559-Screen%20Shot%202015-11-01%20at%208.20.07%20PM.png)

## Packaging for different OS (Standalone applications)
A standalone application specific to target OS can be created with Kivy package manager

1. [OSX](http://kivy.org/docs/guide/packaging-macosx.html)
2. [Linux](http://bitstream.io/packaging-and-distributing-a-kivy-application-on-linux.html)
3. [Windows](http://kivy.org/docs/guide/packaging-windows.html)

## OSx Standalone application
[Modbus-Simulator v0.0.4](https://drive.google.com/open?id=0B8MS3muxUtROTHNMcW00QkNJdDQ)

# NOTE:
Tested only on OSX