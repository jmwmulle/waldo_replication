__author__ = "Jon Mulle"

import klibs
from klibs.KLExceptions import *
from klibs import Params
from klibs.KLUtilities import *
from klibs.KLNumpySurface import NumpySurface
import klibs.KLDraw as kld

#  Below are some commonly required additional libraries; uncomment as needed.

# import os
# import time
# from PIL import Image
# import sdl2
# import sdl2.ext
# import numpy
# import math
# import aggdraw
import random



Params.default_fill_color = (100, 100, 100, 255)  # TODO: rotate through seasons
Params.collect_demographics = True
Params.practicing = False
Params.eye_tracking = True
Params.eye_tracker_available = True
Params.pre_render_block_messages = True

Params.blocks_per_experiment = 4
Params.trials_per_block = 2
Params.practice_blocks_per_experiment = 1
Params.trials_per_practice_block = 1
Params.manual_trial_generation = False

# I hate retyping strings.
LOC = "location"
AMP = "amplitude"
ANG = "angle"
NEW = "new"
OLD = "old"


def line_segment_len(a, b):
	y = b[1] - a[1]
	x = b[0] - a[0]
	return math.sqrt(y**2 + x**2)


def null_trial_generator(exp_factors):
	blocks = []
	for i in range(Params.blocks_per_experiment):
		block = []
		for j in range(Params.trials_per_block):
			block.push([])
		blocks.push(block)
	return blocks


class WaldoReplication(klibs.Experiment):
	max_amplitude_deg = 8  # degrees of visual angle
	min_amplitude_deg = 2  # degrees of visual angle
	max_amplitude = None  # px
	min_amplitude = None  # px
	min_saccades = 5
	max_saccades = 12
	dot_diameter_deg = 0.5
	dot_diameter = None
	search_disc = None
	screen_pad = None
	min_fixation = 20
	max_fixation = 500
	allow_intermittent_bg = True
	fixation_boundary_tolerance = 3  # if drift_correct target too small to fixate, use this to scale boundary (not image)
	disc_boundary_tolerance = 1.5  # if drift_correct target too small to fixate, use this to scale boundary (not image)
	unfound_target_timeout = 2.5  # seconds
	looked_away_msg = None
	eyes_moved_message = None

	# trial vars
	locations = []
	trial_type = None
	backgrounds = {}
	bg = None
	bg_state = None
	saccade_count = None
	frame_size = "1024x768"
	n_back = None

	def __init__(self, *args, **kwargs):
		super(WaldoReplication, self).__init__(*args, **kwargs)
		self.max_amplitude = deg_to_px(self.max_amplitude_deg)
		self.min_amplitude = deg_to_px(self.min_amplitude_deg)
		self.dot_diameter = deg_to_px(self.dot_diameter_deg)
		self.screen_pad = self.dot_diameter * 1.5
		self.search_disc = kld.Annulus(self.dot_diameter * 3, 10, fill=[0, 0, 0, 255])
		self.mouse_dot = kld.Circle(12, [3, [0, 0, 0]], [255, 0, 0])

	def setup(self):
		Params.key_maps['WaldoReplication_response'] = klibs.KeyMap('WaldoReplication_response', [], [], [])
		self.fill(Params.default_fill_color)
		self.text_manager.add_style("msg", 64, [245,255,235,255])
		self.looked_away_msg = self.message("Looked away too soon.", "msg", blit=False)
		self.message("Loading, please hold...", "msg")
		self.flip(0.1)
		if not Params.testing:
			scale_images = False
			for i in range(1, 10):
				pump()
				image_key = "wally_0{0}".format(i)
				#  there are 3 sizes of image included by default; if none match the screen res, choose 1080p then scale
				image_f = os.path.join(Params.image_dir, image_key, "{0}x{1}.jpg".format(Params.screen_x, Params.screen_y))
				if not os.path.isfile(image_f):
					image_f = os.path.join(Params.image_dir, image_key, "1920x1080.jpg")
					scale_images = True
				self.backgrounds[image_key] = ([image_key, NumpySurface(image_f)])
				if scale_images:
					self.backgrounds[image_key][1].scale( Params.screen_x_y )
				self.backgrounds[image_key][1] = self.backgrounds[image_key][1].render()
		message_format = {"color": [255, 255, 255, 255],
		  "font_size": 64,
		  "blit": False}
		self.eyes_moved_message = self.message("Looked away too soon.", **message_format)

	def block(self, block_num):
		self.block_break()

	def trial_prep(self, trial_factors):
		self.database.init_entry('trials')
		self.trial_type = trial_factors[2]
		self.n_back = int(trial_factors[4])
		self.saccade_count = self.generate_locations(random.choice(range(self.min_saccades, self.max_saccades)))
		self.bg_state = trial_factors[3]
		self.bg = self.backgrounds[trial_factors[1]]
		for l in self.locations:
			boundary_name = "saccade_{0}".format(self.locations.index(l))
			padded_disc_projection = int((self.search_disc.surface_width * self.disc_boundary_tolerance) // 2)
			x1 = l[LOC][0] - padded_disc_projection
			x2 = l[LOC][0] + padded_disc_projection
			y1 = l[LOC][1] - padded_disc_projection
			y2 = l[LOC][1] + padded_disc_projection
			self.eyelink.add_gaze_boundary(boundary_name, [(x1, y1), (x2, y2)], EL_RECT_BOUNDARY)
		x1 = Params.screen_c[0] - kld.drift_correct_target().width * self.fixation_boundary_tolerance
		y1 = Params.screen_c[1] - kld.drift_correct_target().height * self.fixation_boundary_tolerance
		x2 = Params.screen_c[0] + kld.drift_correct_target().width * self.fixation_boundary_tolerance
		y2 = Params.screen_c[1] + kld.drift_correct_target().height * self.fixation_boundary_tolerance
		self.eyelink.add_gaze_boundary("trial_fixation", [(x1, y1), (x2, y2)], EL_RECT_BOUNDARY)
		self.drift_correct()

	def trial(self, trial_factors):
		self.refresh_background(False, True, True)
		fixate_interval = Params.tk.countdown(0.7)
		self.eyelink.start(Params.trial_number)
		while fixate_interval.counting():
			if not self.eyelink.within_boundary("trial_fixation"):
				error_msg_countdown = Params.tk.countdown(1)
				while error_msg_countdown.counting():
					self.fill([255, 0, 0])
					self.blit(self.looked_away_msg, location="center", registration="center")
					self.flip()
				raise TrialException("Gaze out of bounds.")
			else:
				self.refresh_background(False, True, True)
		self.refresh_background()
		rt = -1
		location = None
		visited_locations = 0  # on OLD trials, matching self.locations.index(l) to len(self.locations) - 1 doesn't work
		timed_out = False
		for l in self.locations:
			visited_locations += 1
			boundary = "saccade_{0}".format(self.locations.index(l))
			dot_interval = Params.tk.countdown(0.500)
			fixated = False
			elapsed = False
			timeout_countdown = Params.tk.countdown(self.unfound_target_timeout)
			Params.tk.start('rt')	
			rt_start = time.time()
			while not (fixated and elapsed):
				if not timeout_countdown.counting():
					timed_out = True
					break
				elapsed = not dot_interval.counting()
				gaze = self.eyelink.gaze()
				fixated = self.eyelink.within_boundary(boundary, gaze)
				if fixated and rt == -1:
					if visited_locations == len(self.locations):
						Params.tk.stop('rt')
						rt = Params.tk.period('rt')
						rt = time.time() - rt_start
						location = l
				rem_bg = False if visited_locations < len(self.locations) or self.bg_state == "present" else True
				self.refresh_background(rem_bg, flip=True, disc_loc=l[LOC])
				event_stack = sdl2.ext.get_events()
				for e in event_stack:
					self.ui_request(e)
				pump()
				# if visited_locations == len(self.locations):
				# 	Params.tk.stop('rt')
				# 	rt = Params.tk.period('rt')
				# 	location = l
		if timed_out or location is None:
			location = {AMP:-1, ANG: -1, LOC: (-1,-1)}
		
		self.eyelink.stop()		

		return {"trial_num": Params.trial_number,
				"block_num": Params.block_number,
				"bg_image": self.bg[0],
				"timed_out": str(timed_out),
				"rt": rt,
				"target_type": self.trial_type,
				"bg_state": self.bg_state,
				"n_back": self.n_back,
				"amplitude": px_to_deg(location[AMP]),
				"angle": location[ANG],
				"saccades": len(self.locations)}

	def trial_clean_up(self, trial_id, trial_factors):
		if trial_id:  # ie. if this isn't a recycled trial
			index = 0
			for loc in self.locations:
				l = {
					'participant_id': Params.participant_id,
					'trial_id': trial_id,
					'trial_num': Params.trial_number,
					'block_num': Params.block_number,
					'location_num': index + 1,
					'x': loc[LOC][0],
					'y': loc[LOC][1],
					'amplitude': loc[AMP],
					'angle': loc[ANG],
					'n_back': self.saccade_count - (self.n_back + 2) == index,
					'penultimate': index + 2 == self.saccade_count,
					'final': index + 1 == self.saccade_count,
				}
				index += 1
				self.database.insert(l, 'trial_locations', False)
		self.eyelink.clear_gaze_boundaries()
		self.locations = None
		self.trial_type = None
		self.bg = None
		self.bg_state = None
		self.saccade_count = None
	
	def clean_up(self):
		pass

	def refresh_background(self, remove_bg=False, drift_correct=False, flip=False, disc_loc=None):
		self.fill()
		if drift_correct:
			self.blit(kld.drift_correct_target(), position=Params.screen_c, registration=5)
		if self.bg_state != "absent" and remove_bg is False: self.blit(self.bg[1])
		if not Params.eye_tracker_available:
			self.blit(self.mouse_dot, position=mouse_pos(), registration=5)
		if disc_loc:
			self.blit(self.search_disc, position=disc_loc, registration=5)
		if flip:
			self.flip()

	# Following two functions are used in setup and trial prep to generate the saccade path, not used in trial
	def generate_locations(self, saccade_count):
		self.locations = []
		n_back_index = saccade_count - (2 + self.n_back)  # 1 for index, 1 b/c  n_back counts from penultimate saccade
		while len(self.locations) != saccade_count:
			try:
				prev_loc = self.locations[-1][LOC]
			except IndexError:
				prev_loc = Params.screen_c  # for the initial location
			angle = random.choice(range(0, 360))
			amplitude = random.choice(range(self.min_amplitude, self.max_amplitude))
			location = self.new_location(prev_loc, angle, amplitude)
			try:
				n_back = self.locations[n_back_index]
			except IndexError:
				n_back = None
			####### FINAL SACCADE ######
			if len(self.locations) == saccade_count - 1 and n_back is not None:
				if self.trial_type > 0:  # ie. angle > 0: new location, angle == 0: n-back
					amplitude = int(math.ceil(line_segment_len(n_back[LOC], prev_loc)))
					angles = [(a + self.locations[-1][ANG] % 90) % 360 for a in range(0, 360, 60)]
					possible_locations = [self.new_location(prev_loc, a, amplitude) for a in angles]
					location = random.choice(possible_locations)
					angle = possible_locations.index(location) * 60
				else:
					location = n_back[LOC]
					angle = n_back[ANG]
					amplitude = n_back[AMP]

			####### PENULTIMATE SACCADE ######
			if len(self.locations) == saccade_count - 2 and location is not False:
				radius = line_segment_len(n_back[LOC], location)
				boundary_test = [location[0] + radius < Params.screen_x - self.screen_pad,
								 location[0] - radius > self.screen_pad,
								 location[1] + radius < Params.screen_y - self.screen_pad,
								 location[1] - radius > self.screen_pad]
				if all(boundary_test) is not True: location = None

			if location:
				self.locations.append({LOC: location, AMP: amplitude, ANG: angle})
		return saccade_count

	def new_location(self, prev_loc, angle, amplitude):
		if angle % 90:
			quadrant_angle = angle
			# note that x_sign is inverted because screen pixels are uppermost at 0
			x_sign = -1
			y_sign = 1
			if angle > 90:
				if angle < 180:
					x_sign = 1
					y_sign = 1
					quadrant_angle = 90 - (angle - 90)
				elif angle < 270:
					x_sign = 1
					y_sign = -1
					quadrant_angle = angle - 180
				else:
					x_sign = -1
					y_sign = -1
					quadrant_angle = 90 - (angle - 270)
			A = math.radians(float(quadrant_angle))
			B = math.radians(float(90 - quadrant_angle))
			d_x = int(math.sin(B) * amplitude) * x_sign
			d_y = int(math.sin(A) * amplitude) * y_sign
			x_loc = prev_loc[0] + d_x
			y_loc = prev_loc[1] + d_y
		else:
			if angle in (0, 360):
				x_loc = prev_loc[0] - amplitude
				y_loc = prev_loc[1]
			elif angle == 90:
				x_loc = prev_loc[0]
				y_loc = prev_loc[1] + amplitude
			elif angle == 180:
				x_loc = prev_loc[0] + amplitude
				y_loc = prev_loc[1]
			else:
				x_loc = prev_loc[0]
				y_loc = prev_loc[1] - amplitude
		x_ok = self.screen_pad < x_loc < Params.screen_x - self.screen_pad 
		y_ok = self.screen_pad < y_loc < Params.screen_y - self.screen_pad
		if x_ok and y_ok:
			return [x_loc, y_loc]
		return False

