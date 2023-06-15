import time
import csv
import CastleSerialLinkControl
import math
from tkinter import Tk, Label, Entry, Button, StringVar
import threading
import os
import serial
import serial.tools.list_ports

Ki = 1
dt = 0.1  # Change this to 0.1 for a 100ms interval
baseline_throttle = 4000
integrator = baseline_throttle

output_folder = '/Users/abdelmaleksaadidrissi/Documents/'
# MB: The following line lists individual COM ports, but if you are using the FTDI
# there will only be one which has the Serial links on it. Individual Serial Link/ESC
# pairs will all be sharing the same COM port. I would replace with:
#
# serial_port = serial.Serial("COM#", baudrate=115200, timeout=1) # where "#" matches the 0,1,2,etc value of the actual FTDI COM port
#
ports = list(serial.tools.list_ports.comports())
serial_links = []

# MB: since all of these will be on the same COM port, you should not loop through COMs, but
# over device IDs. You will need to change each Serial Link ID using the Castle Link, then loop
# through the range of IDs. E.g.:
#
# serial_link_ids = [0, 1]
# for id in serial_link_ids:
#   serial_links.append(CastleSerialLinkControl.SerialLink(serial_port, device_id=id))
for port in ports:
    ser = serial.Serial(port.device, baudrate=115200, timeout=1)
    serial_links.append(CastleSerialLinkControl.SerialLink(ser, device_id=0))

print(serial_links[0].read_var("speed"))
print(serial_links[0].read_var("voltage"))

error = [0] * len(serial_links)
throttle_command = [0] * len(serial_links)
rpm_command = 5000
collect_data = False
start_time = 0
data_buffer = [[] for _ in range(len(serial_links))]
file_name_third_component = 'default'

def update_rpm():
    global rpm_command
    rpm_command = int(rpm_entry.get())

def update_name():
    global file_name_third_component
    file_name_third_component = str(name_entry.get())

def start_collecting():
    global collect_data, start_time
    collect_data = True
    start_time = time.time()

def stop_collecting():
    global collect_data, rpm_command, data_buffer, file_name_third_component
    collect_data = False

    # Write data for each motor
    for i, buffer in enumerate(data_buffer):
        motor_data = buffer
        output_file_name = f'testdata_{rpm_command}_motor{i+1}_{file_name_third_component}.csv'
        output_path = os.path.join(output_folder, output_file_name)
        with open(output_path, 'w', newline='') as output_file:
            writer = csv.writer(output_file)
            writer.writerow(['Timestamp', 'RPM', 'Throttle'])
            for row in motor_data:
                writer.writerow(row)

    data_buffer = [[] for _ in range(len(serial_links))]

def control_loop():
    global error, throttle_command, integrator
    try:
        while True:
            current_rpms = []
            for i, serial_link in enumerate(serial_links):
                current_rpm = serial_link.read_var("speed") / 2
                current_rpms.append(current_rpm)
                print(f"Motor {i + 1} RPM: {current_rpm}")
                error[i] = rpm_command - current_rpm
                integrator += error[i] * Ki * dt
                throttle_command[i] = math.floor(integrator)

                if collect_data:
                    elapsed_time = round((time.time() - start_time) * 10, 1)  # Calculate elapsed time in tenths of a second
                    data_buffer[i].append([elapsed_time, current_rpm, throttle_command[i]])

                print(f"Motor {i + 1} Throttle: {throttle_command[i]}")
                serial_link.write_var("write throttle", throttle_command[i])
                time.sleep(dt)

        time.sleep(5)
    finally:
        for serial_link in serial_links:
            serial_link.write_var("write throttle", 0)

# MB: I would *highly* recommend waiting to work on a GUI until after you have the core functionality working.
# Instead just write some test script that updates rpm_command using delays.
#
# Also: multi-threaded code (which you will need with an event-based GUI) has lots of complicated problems that can arise,
# I would highly recommend reading up on thread-safe programming including use of mutexes or queues for variables accessible from
# multiple threads. Globals are generally unsafe to modify and access from two separate threads, and may work most of the
# time but occasionally fail depending on when threads switch. This seems to cover a little bit specifically for Tkinter:
# https://codeahoy.com/learn/tkinter/ch5/#moving-stuff-from-threads-to-tkinter
def create_gui():
    global rpm_entry, name_entry, data_buffer
    root = Tk()
    root.geometry("400x300")
    rpm_label = Label(root, text="RPM Command")
    rpm_label.pack()
    rpm_entry = Entry(root)
    rpm_entry.pack()
    rpm_entry.insert(0, "7000")
    rpm_button = Button(root, text="Update RPM", command=update_rpm)
    rpm_button.pack()

    name_label = Label(root, text="File Name Third Component")
    name_label.pack()
    name_entry = Entry(root)
    name_entry.pack()
    name_entry.insert(0, "default")
    name_button = Button(root, text="Update Name", command=update_name)
    name_button.pack()

    collect_button = Button(root, text="Collect Data", command=start_collecting)
    collect_button.pack()
    stop_collect_button = Button(root, text="Stop Collecting", command=stop_collecting)
    stop_collect_button.pack()

    elapsed_time_label = Label(root, text="")
    elapsed_time_label.pack()

    def update_elapsed_time():
        if collect_data:
            elapsed_time = round((time.time() - start_time) * 10, 1)
            elapsed_time_label.config(text=f"Elapsed Time: {elapsed_time} tenths of a second")
        root.after(100, update_elapsed_time)

    update_elapsed_time()
    root.mainloop()

control_thread = threading.Thread(target=control_loop)
control_thread.start()

create_gui()