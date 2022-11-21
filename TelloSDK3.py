# -*- coding: utf-8 -*-

import socket
import threading
import time
import numpy as np
import cv2
from typing import Optional, Union, Type, Dict

class Tello:

	def __init__(self, tello_ip='192.168.10.1', tello_cmd_port=8889, tello_info_port=8890, tello_video_port=11111):
		"""
		Puts the Tello into SDK mode and binds to the local IP/port 
		
		:param command_timeout (float): Timeout seconds.
		:param tello_ip (str): Tello's IP address.
		:param tello_cmd_port (int): Tello's UDP port.
		:param tello_info_port (int): UDP receive port.
		:param tello_video_port (int): UDP receive port.
		"""
		
		self.abort_flag = False
		#self.command_timeout = command_timeout
		
		self.response = None  
		self.state = None
		
		self.frame = None  # numpy array BGR -- current camera output frame
		
		# Conversion functions for state protocol fields
		INT_STATE_FIELDS = (
			# Tello EDU with mission pads enabled only
			'mid', 'x', 'y', 'z',
			# 'mpry': (custom format 'x,y,z')
			# Common entries
			'pitch', 'roll', 'yaw',
			'vgx', 'vgy', 'vgz',
			'templ', 'temph',
			'tof', 'h', 'bat', 'time'
		)
		FLOAT_STATE_FIELDS = ('baro', 'agx', 'agy', 'agz')
		
		self.state_field_converters: Dict[str, Union[Type[int], Type[float]]]
		self.state_field_converters = {key : int for key in INT_STATE_FIELDS}
		self.state_field_converters.update({key : float for key in FLOAT_STATE_FIELDS})
		
		# Tello address
		self.tello_address = (tello_ip, tello_cmd_port)
		
		# create sockets
		self.socket_cmd   = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)  # socket for sending cmd
		self.socket_info  = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)  # socket for receiving status infomation
		
		self.last_height = 0
		
		# thread for receiving cmd ack
		self.socket_cmd.bind(('', tello_cmd_port))
		self.receive_cmd_thread = threading.Thread(target=self._receive_cmd_thread)
		self.receive_cmd_thread.daemon = True
		self.receive_cmd_thread.start()
		
		# thread for receiving status info
		self.socket_info.bind(('', tello_info_port))
		self.receive_info_thread = threading.Thread(target=self._receive_info_thread)
		self.receive_info_thread.daemon = True
		self.receive_info_thread.start()
		
		# for thread for receiving video by opencv
		self.udp_video_address = 'udp://@0.0.0.0:' + str(tello_video_port)
		self.cap = None
		self.video_loop = False
		
		# thread for avoid 15 second limit
		self.send_cmd_thread = threading.Thread(target=self._send_cmd_thread)
		self.send_cmd_thread.daemon = True
		self.send_cmd_thread.start()

	def __del__(self):
		"""Closes the local socket."""
		if self.cap is not None:
			self.cap.release()
		
		self.socket_cmd.close()
		self.socket_info.close()

	def connect(self):
		return self.send_command('command')

	def send_command(self, command, timeout=5):
		print ("[info] send cmd: {}".format(command))
		self.abort_flag = False

		def set_abort_flag():
			self.abort_flag = True

		timer = threading.Timer(timeout, set_abort_flag)

		self.socket_cmd.sendto(command.encode('utf-8'), self.tello_address)

		timer.start()
		while self.response is None:
			if self.abort_flag is True:
				break
		timer.cancel()
		
		if self.response is None:
			response = 'none_response'
		else:
			response = self.response.decode('utf-8')

		self.response = None

		return response

	def get_response(self):
		response = self.response
		return response

	# Thread function
	def _receive_cmd_thread(self):
		while True:
			try:
				self.response, ip = self.socket_cmd.recvfrom(3000)
				#print(self.response)
			except socket.error as exc:
				print ("Caught exception socket.error : %s" % exc)

	def _receive_info_thread(self):
		while True:
			try:
				data, ip = self.socket_info.recvfrom(3000)
				#print(data)
				state = data.decode('utf-8')
				state = state.strip()
				#print(state)
				if state == 'ok':
					continue

				state_dict = {}
				for field in state.split(';'):
					split = field.split(':')
					if len(split) < 2:
						continue

					key = split[0]
					value: Union[int, float, str] = split[1]

					if key in self.state_field_converters:
						num_type = self.state_field_converters[key]
						try:
							value = num_type(value)
						except ValueError as e:
							
							continue

					state_dict[key] = value                

				#print(state_dict)

			except socket.error as exc:
				print ("Caught exception socket.error : %s" % exc)

	def _send_cmd_thread(self):
		while True:
			time.sleep(10)
			self.send_command('command')

	# System control command
	def motoron(self):
		self.send_command('motoron')

	def motoroff(self):
		self.send_command('motoroff')

	def emergency(self):
		self.send_command('emergency')

	def reboot(self):
		self.send_command('reboot')

	# Video streaming
	def streamon(self):
		self.send_command('streamon')
		self.start_video_loop()

	def streamoff(self):
		self.stop_video_loop()
		self.send_command('streamoff')

	def start_video_loop(self):
		self.cap = cv2.VideoCapture(self.udp_video_address)
		self.receive_video_thread = threading.Thread(target=self._receive_video_thread)
		self.receive_video_thread.daemon = True
		self.video_loop = True
		self.receive_video_thread.start()

	def stop_video_loop(self):
		self.video_loop = False
		time.sleep(1)

	def _receive_video_thread(self):
		print("[info] Start video-loop")
		while True:
			if self.video_loop == False:
				break
			
			ret, self.frame = self.cap.read()
		
		self.cap.release()
		self.cap = None
		print("[info] Stop video-loop")

	def read(self):
		return self.frame

	# rc command
	def send_rc_command(self, lr:int, fb:int, ud:int, yaw:int):
		
		def constrain_100(value):
			return min( 100, max( -100, value ) )
		
		cmd = 'rc {} {} {} {}'.format( constrain_100(lr), constrain_100(fb), constrain_100(ud), constrain_100(yaw) )
		self.send_command( cmd )

	# move command
	def takeoff(self):
		return self.send_command('takeoff')

	def throwfly(self):
		return self.send_command('throwfly')

	def land(self):
		return self.send_command('land')

	def move(self, direction, distance):
		distance = int(distance)
		return self.send_command('%s %s' % (direction, distance))

	def move_forward(self, distance):
		return self.move('forward', distance)

	def move_backward(self, distance):
		return self.move('back', distance)

	def move_left(self, distance):
		return self.move('left', distance)

	def move_right(self, distance):
		return self.move('right', distance)

	def move_up(self, distance):
		return self.move('up', distance)

	def move_down(self, distance):
		return self.move('down', distance)

	def rotate_cw(self, degrees):
		return self.send_command('cw %s' % degrees)

	def rotate_ccw(self, degrees):
		return self.send_command('ccw %s' % degrees)

	def flip(self, direction):
		return self.send_command('flip %s' % direction)

	def set_speed(self, speed):
		return self.send_command('speed %s' % speed)

	# go
	def go_xyz_speed(self, x: int, y: int, z: int, speed: int):
		"""Fly to x y z relative to the current position.
		Speed defines the traveling speed in cm/s.
		Arguments:
		    x: -500-500
		    y: -500-500
		    z: -500-500
		    speed: 10-100
		"""
		def constrain_500(value):
			return min( 500, max( -500, value ) )

		def constrain_speed(value, max_val, min_val ):
			return min( max_val, max( min_val, value ) )

		cmd = 'go {} {} {} {}'.format( constrain_500(x), constrain_500(y), constrain_500(z), constrain_speed(speed,100,10) )
		return self.send_command( cmd )

	# curve
	def curve_xyz_speed(self, x1: int, y1: int, z1: int, x2: int, y2: int, z2: int, speed: int):
		"""Fly to x2 y2 z2 in a curve via x2 y2 z2. Speed defines the traveling speed in cm/s.
		- Both points are relative to the current position
		- The current position and both points must form a circle arc.
		- If the arc radius is not within the range of 0.5-10 meters, it raises an Exception
		- x1/x2, y1/y2, z1/z2 can't both be between -20-20 at the same time, but can both be 0.
		Arguments:
		    x1: -500-500
		    x2: -500-500
		    y1: -500-500
		    y2: -500-500
		    z1: -500-500
		    z2: -500-500
		    speed: 10-60
		"""
		def constrain_500(value):
			return min( 500, max( -500, value ) )

		def constrain_speed(value, max_val, min_val ):
			return min( max_val, max( min_val, value ) )

		cmd = 'curve {} {} {} {} {} {} {}'.format( constrain_500(x1), constrain_500(y1), constrain_500(z1), constrain_500(x2), constrain_500(y2), constrain_500(z2), constrain_speed(speed,60,10) )
		return self.send_command( cmd )
	# stop 

	# mission pad command
	# mon
	# moff
	# mdirection x (0/1)

	# go
	# curve
	# jump

	# system setting command
	# wifi ssid pass
	# ap ssid pass
	# port info video
	# setresolution resolution
	# setfps fps high middle low
	# setbitrate bitrate 1-5
	# downvision x  0 1
	def down_vision(self, direction = 0):
		self.send_command('downvision %s' % direction )

	# query command
	def get_speed(self):
		speed = self.send_command('speed?')
		
		try:
			speed = int(speed)
		except:
			pass
		
		return speed

	def get_battery(self):
		battery = self.send_command('battery?')
		
		try:
			battery = int(battery)
		except:
			pass
		
		return battery

	def get_flight_time(self):
		flight_time = self.send_command('time?')
		
		try:
			flight_time = int(flight_time)
		except:
			pass
		
		return flight_time

	def get_height(self):
		height = self.send_command('height?')
		height = str(height)
		height = filter(str.isdigit, height)
		try:
			height = int(height)
			self.last_height = height
		except:
			height = self.last_height
			pass
		return height

	def get_temp(self):
		temp = self.send_command('temp?')
		
		try:
			temp = int(temp)
		except:
			pass
		
		return temp

	def get_attitude(self):
		attitude = self.send_command('attitude?')
		return attitude[:-1]

	def get_baro(self):
		baro = self.send_command('baro?')
		
		try:
			baro = int(baro)
		except:
			pass
		
		return baro

	def get_tof(self):
		tof = self.send_command('tof?')
		
		try:
			tof = int(tof[:-4])/10
		except:
			pass
		
		return tof

	def get_active(self):
		active = self.send_command('active?')
		return active

	def get_wifi(self):
		snr = self.send_command('wifi?')
		
		try:
			snr = int(snr)
		except:
			pass
		
		return snr

	def get_sdk(self):
		sdk = self.send_command('sdk?')
		return sdk

	def get_sn(self):
		sn = self.send_command('sn?')
		return sn

	def get_hardware(self):
		hardware = self.send_command('hardware?')
		return hardware[:-1]

