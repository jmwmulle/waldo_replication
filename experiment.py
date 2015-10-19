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

Params.debug_level = 3

Params.collect_demographics = False
Params.practicing = False
Params.eye_tracking = True
Params.eye_tracker_available = False

Params.blocks_per_experiment = 1
Params.trials_per_block = 5
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
	n_back = 1
	dot_diameter_deg = 0.5
	dot_diameter = None
	dot = None
	screen_pad = None
	min_fixation = 20
	max_fixation = 500
	allow_intermittent_bg = True

	# trial vars
	locations = []
	trial_type = None
	backgrounds = {}
	bg = None
	bg_state = None
	saccade_count = None

	def __init__(self, *args, **kwargs):
		super(WaldoReplication, self).__init__(*args, **kwargs)
		self.max_amplitude = deg_to_px(self.max_amplitude_deg)
		self.min_amplitude = deg_to_px(self.min_amplitude_deg)
		self.dot_diameter = deg_to_px(self.dot_diameter_deg)
		self.screen_pad = self.dot_diameter // 2
		# self.trial_factory.trial_generation_function = null_trial_generator
		# self.trial_factory.generate()
		# circle_vars = {"diameter": self.dot_diameter * 2,
		# 			   "stroke": ,
		# 			   "fill": [255, 0, 0]}
		self.dot = kld.Circle(self.dot_diameter * 3, (8, [255, 255, 255]), [255, 0, 0, 255])
		self.image_dir = os.path.join(Params.asset_path, "image", "waldo_test")

	def setup(self):
		Params.key_maps['WaldoReplication_response'] = klibs.KeyMap('WaldoReplication_response', [], [], [])
		self.fill(Params.default_fill_color)
		msg_format = {"color": [245, 255, 235, 255],
				  "location": Params.screen_c,
				  "registration": 5,
				  "font_size": 64}
		self.message("Loading, please hold...", **msg_format)
		self.flip(0.1)
		if not Params.testing:
			for i in range(1, 8):
				pump()
				image_f = "test_waldo_{0}.jpg".format(i)
				self.backgrounds[image_f] = ([image_f, NumpySurface(os.path.join(self.image_dir, image_f))])
				print self.backgrounds[image_f][1].height
				print self.backgrounds[image_f][1].width
				self.backgrounds[image_f][1].scale( Params.screen_x_y )
	def block(self, block_num):
		pass

	def trial_prep(self, trial_factors):
		self.database.init_entry('trials')
		self.trial_type = trial_factors[2]
		self.saccade_count = self.generate_locations(random.choice(range(self.min_saccades, self.max_saccades)))
		self.bg_state = trial_factors[3]
		self.bg = self.backgrounds[trial_factors[1]]
		for l in self.locations:
			boundary_name = "saccade_{0}".format(self.locations.index(l))
			x1 = l[LOC][0] - self.dot.width // 2
			x2 = l[LOC][0] + self.dot.width // 2
			y1 = l[LOC][1] - self.dot.height // 2
			y2 = l[LOC][1] + self.dot.height // 2
			self.eyelink.add_gaze_boundary(boundary_name, [(x1, y1), (x2, y2)], EL_RECT_BOUNDARY)
		self.drift_correct()

	def trial(self, trial_factors):
		self.refresh_background()
		self.blit(kld.drift_correct_target(), position=Params.screen_c, registration=5)
		self.flip()
		fixate_interval = Params.tk.countdown(0.7)
		while fixate_interval.counting():
			if not self.eyelink.within_boundary("custom_dc_0"):
				self.fill([255, 0, 0])
				message_format = {"color": [255, 255, 255, 255],
								  "font_size": 64,
								  "registration": 5,
								  "location": Params.screen_c}
				self.message("Looked away too soon.", **message_format)
				self.flip(1)
				raise TrialException("Gaze out of bounds.")
			else:
				self.refresh_background()
				self.blit(kld.drift_correct_target(), position=Params.screen_c, registration=5)
		self.fill()
		if self.bg_state != "absent": self.blit(self.bg[1])
		rt = None
		location = None
		visited_locations = 0  # on OLD trials, matching self.locations.index(l) to len(self.locations) - 1 doesn't work
		for l in self.locations:
			visited_locations += 1
			boundary = "saccade_{0}".format(self.locations.index(l))
			Params.tk.start('rt')
			dot_interval = Params.tk.countdown(0.500)
			while dot_interval.counting():
				self.refresh_background()
				self.flip()
			while not self.eyelink.within_boundary(boundary):
				pump()
				event_stack = sdl2.ext.get_events()
				for e in event_stack:
					self.over_watch(e)
				self.refresh_background(self.bg_state)
				self.blit(self.dot, position=l[LOC], registration=5)
				self.flip()
			Params.tk.stop('rt')
			if visited_locations == len(self.locations):
				rt = Params.tk.period('rt')
				location = l
		return {"trial_num": Params.trial_number,
				"block_num": Params.block_number,
				"bg_image": self.bg[0],
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
		self.locations = []
		self.trial_type = None
		self.bg = None
		self.bg_state = None
		self.saccade_count = None


	def clean_up(self):
		pass

	def refresh_background(self, remove_bg=False):
		self.fill()
		if self.bg_state != "absent" and remove_bg is False: self.blit(self.bg[1])
		if not Params.eye_tracker_available:
			self.blit(kld.Circle(12, [3, [0, 0, 0]], [255, 0, 0]), position=mouse_pos(), registration=5)

	# Following two functions are used in setup and trial prep to generate the saccade path, not used in trial
	def generate_locations(self, saccade_count):
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
			if len(self.locations) == saccade_count - 1:
				if self.trial_type == NEW:
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
			x_loc = prev_loc[0] - d_x
			y_loc = prev_loc[1] - d_y
		else:
			if angle in (0, 360):
				x_loc = prev_loc[0] + amplitude
				y_loc = prev_loc[1]
			elif angle == 90:
				x_loc = prev_loc[0]
				y_loc = prev_loc[1] + amplitude
			elif angle == 180:
				x_loc = prev_loc[0] - amplitude
				y_loc = prev_loc[1]
			else:
				x_loc = prev_loc[0]
				y_loc = prev_loc[1] - amplitude
		if 0 < x_loc < Params.screen_x - self.screen_pad and 0 < y_loc < Params.screen_y - self.screen_pad:
			return [x_loc, y_loc]
		return False

