# Brett Leaver
# 2018-1014

from tkinter import Canvas, Tk, CENTER
from PIL import ImageTk, Image
from numpy import array

# this is a simple subclass of the tk canvas that acts as a basic image viewer
# the image can be panned and zoomed around. It can be subclassed to add extra functionality
class image_viewer(Canvas):
	def __init__(self, master, i, width=512, height=512, **kwargs):
		Canvas.__init__(self, master, width=width, height=height, highlightthickness=0, **kwargs)
		
		# bind mouse events to functions
		self.bindings()
		
		# get position of tkinter event
		self.earr = lambda x : array([x.x, x.y])
		
		# copy of the image being viewed
		self.image = i
		
		# size of the viewer
		self.canvas_size = array([width,height])
		
		# position from center of canvas
		self.rel_position = array([0.0,0])
		
		# previous position, used for dragging mouse
		self.last_rel_position = array([0,0])
		
		# scale of the image
		self.scale = 1
		
		# what to multiply/divide the scale by when increasing/decreasing
		self.scale_step = 15/8
		
		# minimum allowed scale for image
		self.min_scale = 1/8
		
		# maximum allowed scale for image
		self.max_scale = 20
		
		# offset used for removing the parts of the image outside of the canvas
		# probably don't change this unless debugging calculate_crop_extra()
		self.crop_padding = -1
		
		# distance from edge that the image is not allowed to cross
		self.pan_boundary = 50

		self.draw()

	# the origin. The default is top left, so this is needed to center the image
	def position_offset(self):
		return self.canvas_size/2

	# get the position of the image with respect to the new origin
	def position(self):
		return self.rel_position + self.position_offset()

	# mouse events
	def bindings(self):
		# mouse clicked, redraw image and start dragging
		self.bind("<Button-1>", self.click)

		# scroll up, zoom in
		self.bind("<Button-5>", self.wheel_up)

		# scroll down, zoom out
		self.bind("<Button-4>", self.wheel_down)

		# left drag, pan the image
		self.bind("<B1-Motion>", self.drag)

		# redraw and update size when window is resized
		self.bind("<Configure>", self.configure)

	# update canvas_size and redraw when window is resized
	def configure(self, event):
		self.canvas_size = array([event.width, event.height])
		self.draw()

	# convert a point relative to the image origin to a point on the canvas
	def image_to_canvas(self, point):
		return (point*self.scale)+self.position()

	# convert a point on the canvas to a point relative to the image origin
	def canvas_to_image(self, point):
		return (point-self.position())/self.scale

	def calculate_crop_extra(self):
		# size of the image, before scale
		size = array(self.image.size)
		
		# how far in from each edge to remove when cropping
		left_inset, right_inset, top_inset, bottom_inset = 0, 0, 0, 0

		# how far to adjust image position away from each edge
		# this is needed becasuse cropping the image changes its size,
		# causing it to shift around when cropped and centered
		# also, it is needed to account for precision loss caused by crop
		left_offset, right_offset, top_offset, bottom_offset = 0, 0, 0, 0

		# the position of the top left corner of the image, after being scaled, if it were not to be cropped
		new_a = self.position() - size / 2 * self.scale

		# the position of the bottom right corner of the image, after being scaled, if it were not to be cropped
		new_b = self.position() + size / 2 * self.scale
		
		# how many (scaled) pixels to leave on the outside when cropping. 1 is enough
		scaled_padding = self.crop_padding * self.scale

		# if the edge is off the screen, calculate by how much
		# removing this will cause the image to shift when it's re-aligned by its new center
		# also, calculate how much error there will be so it can be accounted for
		# if the image is scaled, often the amount extending past the screen will not be a whole number
		# since only whole numbers of pixels can be removed from the image, it is necessary to shift the
		# image over to account for the missing fraction of a pixel that could not be cropped
		# do this for all edges
		if new_a[0] < 0:
			left_inset = (scaled_padding - new_a[0]) / self.scale
			left_offset = ((left_inset) * self.scale / 2) + (-left_inset + round(left_inset)) * self.scale / 2
		if new_a[1] < 0:
			top_inset = (scaled_padding - new_a[1]) / self.scale
			top_offset = ((top_inset) * self.scale / 2) + (-top_inset + round(top_inset)) * self.scale / 2 
		if new_b[0] > self.canvas_size[0]:
			right_inset = (new_b[0] - self.canvas_size[0] + scaled_padding) / self.scale
			right_offset = ((right_inset) * self.scale / 2) + (-right_inset + round(right_inset)) * self.scale / 2 
		if new_b[1] > self.canvas_size[1]:
			bottom_inset = (new_b[1] - self.canvas_size[1] + scaled_padding) / self.scale
			bottom_offset = ((bottom_inset) * self.scale / 2) + (-bottom_inset + round(bottom_inset)) * self.scale / 2 

		# the new bounding box of the image for cropping
		bbox = (left_inset, top_inset, size[0] - right_inset, size[1] - bottom_inset)

		# the offset that should be added to the position so it is displayed properly 
		offset = array([left_offset - right_offset, top_offset - bottom_offset])

		return (bbox, offset)

	# draw the image on the canvas
	def draw_image(self, resample=Image.NONE):
		# make sure it isn't too far off the screen
		self.limit_image_position()

		# create copy of the image to be cropped/scaled
		i = self.image

		# get bounding box and offset
		(bbox, offset) = self.calculate_crop_extra()

		# get the position the image will be displayed at by
		# adding the true position and the offset needed to account for crop bullshit
		render_position = self.position() + offset

		# crop the image
		i = i.crop(bbox)

		# scale the image
		i = i.resize((int(i.size[0] * self.scale),int(i.size[1] * self.scale)), resample)

		# convert to tk PhotoImage
		image_tk = ImageTk.PhotoImage(i)

		# draw the image on the canvas
		self.create_image(render_position[0], render_position[1], image=image_tk, anchor=CENTER)

		# keep a reference to the image so tkinter doesn't fuck it
		self.image_tk = image_tk

	# zoom in
	def wheel_up(self, event):
		# zooming in can be accomplished simply by scaling the image,
		# but when using the scroll wheel on a mouse, it is desirable to
		# have the image be zoomed while keeping the area under the mouse
		# in the same position. This allows the user to zoom in on certain areas
		# without panning around, simply by placing the cursor over the desired area
		# and scrolling. A different method might feel more natural with a trackpad

		# keep the current scale
		old_scale = float(self.scale)

		# increase the scale by multiplying it by scale_step
		new_scale = old_scale * self.scale_step

		# cap its value so it's within the min/max
		if new_scale > self.max_scale:
			new_scale = self.max_scale

		# find what factor the image is being scaled by
		factor = new_scale / old_scale

		# set the scale of the image
		self.scale = new_scale

		# move the image to make it so that the area under the cursor stays put
		# if you aren't using this, simply increasing the scale will work
		# simply increase/decrease and cap the scale value if you aren't doing this
		# most of the above code is just needed to make the factor number correct
		# so it can be used here
		if factor != 1:
			self.rel_position = (self.position() - self.earr(event)) * factor + self.earr(event) - self.position_offset()

		# redraw the image
		self.draw()

	# zoom out
	def wheel_down(self, event):
		# same thing here but in reverse
		old_scale = float(self.scale)
		new_scale = old_scale / self.scale_step
		if new_scale < self.min_scale:
			new_scale = self.min_scale
		factor = new_scale / old_scale
		self.scale = new_scale
		if factor != 1:
			self.rel_position = (self.position() - self.earr(event)) * factor + self.earr(event) - self.position_offset()
		self.draw()

	# mouse clicked
	def click(self, event):
		# redraw image, not really needed
		self.draw()

		# update the previous mouse position
		self.last_rel_position = self.earr(event)

	# mouse dragged, used for panning around
	def drag(self, event):
		# point the mouse was dragged to
		location = self.earr(event)

		# relative amount the mouse was moved since last event
		delta = location - self.last_rel_position

		# save position for next time
		self.last_rel_position = location

		# add the relative change to the position of the image
		self.rel_position += delta

		# redraw image
		self.draw()

	# stop the image from going too far off screen
	def limit_image_position(self):
		# there are many different ways to do this
		# you might want something else so change it if you don't like it

		# size of image
		size = array(self.image.size)

		# position of top left corner
		corner_a = self.position() - size/2*self.scale
		
		# position of bottom right corner
		corner_b = self.position() + size/2*self.scale

		# if the edge has gone too far past the boundary, figure
		# out by how much, and subtract that from its position
		if corner_b[0] < 0 + self.pan_boundary:
			self.rel_position[0] -= corner_b[0] - self.pan_boundary
		if corner_b[1] < 0 + self.pan_boundary:
			self.rel_position[1] -= corner_b[1] - self.pan_boundary
		if corner_a[0] > self.canvas_size[0] - self.pan_boundary:
			self.rel_position[0] -= corner_a[0] - (self.canvas_size[0] - self.pan_boundary)
		if corner_a[1] > self.canvas_size[1] - self.pan_boundary:
			self.rel_position[1] -= corner_a[1] - (self.canvas_size[1] - self.pan_boundary)

	# redraw the image with resampling
	# resampling on every redraw made this too slow, but I
	# put this in because I wanted to be able to click a button
	# to resample the image
	def resample(self):
		self.draw(resample=Image.BICUBIC)

	# draw method. Put other things here if you're displaying things other than the image
	def draw(self, resample=Image.NONE):
		self.draw_image(resample=resample)

# initialize tk
root = Tk()

# open image
i = Image.open("skel.jpg")

# instantiate viewer with image and black background
viewer = image_viewer(root, i, background="black")

# pack it so that it fills the screen
viewer.pack(expand=True, fill="both")

# display
root.mainloop()
