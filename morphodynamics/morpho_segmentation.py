import os
from copy import deepcopy
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
import ipywidgets as ipw
from skimage.segmentation import find_boundaries
import dill
from nd2reader import ND2Reader
import yaml

from .Parameters import Param
from .Dataset import MultipageTIFF, TIFFSeries, ND2
from .folders import Folders

from .Analysis import analyze_morphodynamics
from .morpho_plots import show_windows as show_windows2
from .Windowing import label_windows, calculate_windows_index, create_windows
from .DisplacementEstimation import rasterize_curve, splevper
from . import utils


class InteractSeg():
    def __init__(self, expdir=None, morpho_name=None, signal_name=None):

        """Standard __init__ method.
        Parameters
        ----------
        expdir: str
            path to folder containing data
        morpho_name: str
            name of folder or file used segmentation
        signa_name: list of str
            names of folders or files used as signal
       
        Attributes
        ----------
        """

        style = {'description_width': 'initial'}
        layout = {'width': '300px'}

        self.param = Param(
            expdir=expdir, morpho_name=morpho_name, signal_name=signal_name)

        self.expdir = expdir
        self.param.morpho_name = morpho_name
        self.param.signal_name = signal_name

        self.data = None

        # folders and channel selections
        self.main_folder = Folders(window_width=300)
        self.saving_folder = Folders(window_width=300)

        self.segm_folders = ipw.Select(options=[])
        self.channels_folders = ipw.SelectMultiple(options=[])

        # update choices of segmentation and analysis folders when changin
        # main folder
        self.main_folder.file_list.observe(self.get_folders, names=("options", "value"))
        self.segm_folders.observe(self.update_segm_file_list, names="value")
        self.channels_folders.observe(self.update_signal_file_list, names="value")

        # update saving folder
        self.saving_folder.file_list.observe(self.update_saving_folder, names="options")
        self.update_saving_folder(None)

        # update folder if given at init
        if self.expdir is not None:
            self.expdir = Path(self.expdir)
            self.main_folder.cur_dir = self.expdir
            self.main_folder.refresh(None)

        # export, import buttons
        self.export_button = ipw.Button(description='Save segmentation')
        self.export_button.on_click(self.export_data)

        self.load_button = ipw.Button(description='Load segmentation')
        self.load_button.on_click(self.load_data)

        self.load_params_button = ipw.Button(description='Load parameters')
        self.load_params_button.on_click(self.load_params)
        
        # slider for time limits to analyze
        self.time_slider = ipw.IntSlider(
            description = 'Time', min=0, max=0, value=0, continous_update=False)
        self.time_slider.observe(self.show_segmentation, names='value')

        # intensity sliders
        self.intensity_range_slider = ipw.IntRangeSlider(
            description = 'Intensity range', min=0, max=10, value=0)
        self.intensity_range_slider.observe(self.update_intensity_range, names='value')

        # channel to display
        self.display_channel = ipw.Select(options=[])
        self.segm_folders.observe(self.update_display_channel_list, names="value")
        self.channels_folders.observe(self.update_display_channel_list, names="value")
        self.display_channel.observe(self.update_display_channel, names="value")

        # show windows or nots
        self.show_windows_choice = ipw.Checkbox(description="Show windows", value=True)
        self.show_windows_choice.observe(self.update_windows_vis, names='value')

        # show windows or not
        self.show_text_choice = ipw.Checkbox(description="Show labels", value=True)
        self.show_text_choice.observe(self.update_text_vis, names='value')

        self.width_text = ipw.IntText(value=10, description='Window depth', layout=layout, style=style)
        self.width_text.observe(self.update_params, names='value')

        self.depth_text = ipw.IntText(value=10, description='Window width', layout=layout, style=style)
        self.depth_text.observe(self.update_params, names='value')

        # run the analysis button
        self.run_button = ipw.Button(description='Click to segment')
        self.run_button.on_click(self.run_segmentation)

        # load or initialize
        self.init_button = ipw.Button(description='Initialize data')
        self.init_button.on_click(self.initialize)

        # parameters
        self.maxtime = ipw.IntText(value=0, description='Max time')
        self.maxtime.observe(self.update_data_params, names='value')

        # parameters
        self.step = ipw.IntText(value=1, description='Step')
        self.step.observe(self.update_data_params, names='value')
        
        # parameters
        self.bad_frames = ipw.Text(value='', description='Bad frames (e.g. 1,2,5-8,12)')
        self.bad_frames.observe(self.update_data_params, names='value')

        self.segmentation = ipw.RadioButtons(options=['Thresholding', 'Cellpose'], description='Segmentation:')
        self.segmentation.observe(self.update_params, names='value')

        self.diameter = ipw.FloatText(value=100, description='Diameter:')
        self.diameter.observe(self.update_params, names='value')

        self.out_debug = ipw.Output()
        self.out = ipw.Output()

        with self.out:
            self.fig, self.ax = plt.subplots(figsize=(5, 5))
            self.ax.set_title(f'Time:')
        self.implot = None
        self.wplot = None
        self.tplt = None

    def initialize(self, b=None):
        """Creat a data object based on chosen directories/files"""

        with self.out_debug:
            if os.path.isdir(os.path.join(self.expdir, self.param.morpho_name)):
                self.param.data_type = 'series'
                self.data = TIFFSeries(self.expdir, self.param.morpho_name, self.param.signal_name, data_type=self.param.data_type, step=self.param.step, bad_frames=self.param.bad_frames)

            elif self.param.morpho_name.split('.')[-1] == 'tif':
                self.param.data_type = 'multi'
                self.data = MultipageTIFF(self.expdir, self.param.morpho_name, self.param.signal_name, data_type=self.param.data_type, step=self.param.step, bad_frames=self.param.bad_frames)
            elif self.expdir.split('.')[-1] == 'nd2':
                self.param.data_type = 'nd2'
                self.data = ND2(self.expdir, self.param.morpho_name, self.param.signal_name, data_type=self.param.data_type, step=self.param.step, bad_frames=self.param.bad_frames)

            self.param.max_time = self.data.max_time
            self.maxtime.value = self.data.max_time

    def run_segmentation(self, b=None):
        """Run segmentation analysis"""
        self.run_button.description = 'Segmenting...'
        self.res = analyze_morphodynamics(self.data, self.param)
        self.show_segmentation(change='init')
        self.run_button.description = 'Click to segment'

    def windows_for_plot(self, image, time):

        c = rasterize_curve(
            image.shape, self.res.spline[time], self.res.orig[time])
        w = create_windows(
            c, splevper(self.res.orig[time], self.res.spline[time]),
            self.res.J, self.res.I)
        return w

    def show_segmentation(self, change=None):
        """Update segmentation plot"""

        t = self.time_slider.value
        image = self.load_image(t)
        #image = self.data.load_frame_morpho(t)
        window = self.windows_for_plot(image, t)

        #b0 = find_boundaries(label_windows(image.shape, self.res.windows[t]))
        b0 = find_boundaries(label_windows(image.shape, window))
        b0 = b0.astype(float)
        b0[b0==0] = np.nan

        #windows_pos = calculate_windows_index(self.res.windows[t])
        windows_pos = calculate_windows_index(window)

        with self.out:
            xlim = self.fig.axes[0].get_xlim()
            ylim = self.fig.axes[0].get_ylim()
            
            plt.figure(self.fig.number)
            self.implot, self.wplot, self.tplt = show_windows2(
                        image, window, b0, windows_pos)
            if xlim[1]>1:
                self.fig.axes[0].set_xlim(xlim)
                self.fig.axes[0].set_ylim(ylim)
            self.fig.axes[0].set_title(f'Time:{self.data.valid_frames[t]}')

        # update max slider value with max image value
        self.intensity_range_slider.unobserve_all()
        self.intensity_range_slider.max = int(image.max())
        self.intensity_range_slider.observe(self.update_intensity_range, names='value')

        # when creating image use full intensity values
        if change == 'init':
            self.intensity_range_slider.value = (0, int(image.max()))

        # set new frame to same intensity range as previous frame
        self.implot.set_clim(
            vmin = self.intensity_range_slider.value[0],
            vmax = self.intensity_range_slider.value[1])

    def get_folders(self, change=None):
        '''Update folder options when selecting new main folder'''

        # if an nd2 file is selected, load it, and use metadata channels as choices
        if len(self.main_folder.file_list.value) > 0:
            if (self.main_folder.file_list.value[0]).split('.')[-1] == 'nd2':
                image = ND2Reader(os.path.join(self.main_folder.cur_dir, self.main_folder.file_list.value[0]))
                self.segm_folders.options = image.metadata['channels']
                self.segm_folders.value = None
            
                self.channels_folders.options = image.metadata['channels']
                self.channels_folders.value = ()

                self.expdir = os.path.join(self.main_folder.cur_dir, self.main_folder.file_list.value[0])
                self.param.expdir = self.expdir#.as_posix()
        else:
            folder_names = np.array([x for x in self.main_folder.file_list.options if x[0]!='.' ])

            #self.segm_folders.unobserve(self.update_file_list, names='value')
            self.segm_folders.options = folder_names
            self.segm_folders.value = None
            #self.segm_folders.observe(self.update_file_list, names='value')

            self.channels_folders.options = folder_names

            #self.update_file_list(x)
            self.expdir = self.main_folder.cur_dir
            self.param.expdir = self.expdir.as_posix()

    def update_segm_file_list(self, change = None):
        """Calback to update segmentation file lists depending on selections"""

        self.param.morpho_name = str(self.segm_folders.value)

    def update_signal_file_list(self, change = None):
        """Calback to update signal file lists depending on selections"""

        self.param.signal_name = [str(x) for x in self.channels_folders.value]

    def update_display_channel_list(self, change = None):
        """Callback to update available channels to display"""
        
        self.display_channel.options = [str(self.segm_folders.value)] + [str(x) for x in self.channels_folders.value]
        self.display_channel.value = str(self.segm_folders.value)

    def update_display_channel(self, change=None):

        if self.data is not None:
            self.show_segmentation()

    def load_image(self, time):

        if self.display_channel.value == self.param.morpho_name:
            image = self.data.load_frame_morpho(time)
        else:
            channel_index = self.param.signal_name.index(self.display_channel.value)
            image = self.data.load_frame_signal(channel_index, time)

        return image


    def update_data_params(self, change=None):
        """Callback to update data paramters upon interactive editing"""

        self.param.max_time = self.maxtime.value
        self.param.step = self.step.value

        #parse bad frames
        bads = utils.format_bad_frames(self.bad_frames.value)
        self.param.bad_frames = bads

        #update params
        self.data.update_params(self.param)

        self.time_slider.max = self.data.K-1

    def update_params(self, change=None):
        """Callback to update param paramters upon interactive editing"""

        self.param.cellpose = self.segmentation.value == 'Cellpose'
        self.param.diameter = self.diameter.value
        self.param.width = self.width_text.value
        self.param.depth = self.depth_text.value

    def update_saving_folder(self, change=None):
        """Callback to update saving directory paramters"""

        self.param.resultdir = self.saving_folder.cur_dir

    def update_intensity_range(self, change=None):
        """Callback to update intensity range"""

        self.intensity_range_slider.max = self.implot.get_array().max()
        self.implot.set_clim(
            vmin = self.intensity_range_slider.value[0],
            vmax = self.intensity_range_slider.value[1])
        
    def update_windows_vis(self, change=None):
        """Callback to turn windows visibility on/off"""
        
        self.wplot.set_visible(change['new'])
        
            
    def update_text_vis(self, change=None):
        """Callback to turn windows labels visibility on/off"""
        
        for x in self.tplt:
            x.set_visible(change['new'])
        
    def export_data(self, b):
        """Callback to export data"""
        
        if self.data.data_type == 'nd2':
            del self.data.nd2file
            
        #dill.dump(self.param, open(os.path.join(self.param.resultdir, 'Parameters.pkl'), 'wb'))
        dill.dump(self.res, open(os.path.join(self.param.resultdir, 'Results.pkl'), 'wb'))
        #dill.dump(self.data, open(os.path.join(self.param.resultdir, 'Data.pkl'), 'wb'))
        
        #if self.data.data_type == 'nd2':
        #    self.data.initialize()

        dict_file = {}
        for x in dir(self.param):
            if x[0]=='_':
                None
            elif x == 'resultdir':
                dict_file[x] = getattr(self.param, x).as_posix()
            else:
                dict_file[x] = getattr(self.param, x)

        #del dict_file['resultdir']


        dict_file['bad_frames'] = self.bad_frames.value

        with open(self.saving_folder.cur_dir.joinpath('Parameters.yml'), 'w') as file:
            documents = yaml.dump(dict_file, file)

    def load_data(self, b):
        """Callback to load params, data and results"""

        folder_load = self.main_folder.cur_dir
        #self.param = dill.load(open(os.path.join(folder_load, 'Parameters.pkl'), "rb"))

        self.param, self.res, self.data = utils.load_alldata(folder_load, load_results = True)
        self.param.bad_frames = utils.format_bad_frames(self.param.bad_frames)

        param_copy = deepcopy(self.param)
        self.update_interface(param_copy)
        
        self.show_segmentation(change='init')

    def load_params(self, b):
        """Callback to load only params and data """

        folder_load = self.main_folder.cur_dir
        #self.param = dill.load(open(os.path.join(folder_load, 'Parameters.pkl'), "rb"))
        
        self.param, _, self.data = utils.load_alldata(folder_load, load_results = False)
        
        param_copy = deepcopy(self.param)
        self.update_interface(param_copy)

    def update_interface(self, param_copy):

        self.expdir = Path(param_copy.expdir)

        if self.data.data_type == 'nd2':
            self.main_folder.cur_dir = self.expdir.parent
            self.main_folder.refresh(None)
            self.segm_folders.options = [param_copy.morpho_name]
            self.channels_folders.options = param_copy.signal_name
        else:
            self.main_folder.cur_dir = self.expdir
            self.main_folder.refresh(None)

        # folders
        self.segm_folders.value = param_copy.morpho_name
        self.channels_folders.value = param_copy.signal_name

        if param_copy.cellpose:
            self.segmentation.value = 'Cellpose'
        else:
            self.segmentation.value = 'Thresholding'
        self.diameter.value = param_copy.diameter
        self.width_text.value = param_copy.width
        self.depth_text.value = param_copy.depth
        self.maxtime.value = param_copy.max_time
        self.bad_frames.value = param_copy.bad_frames_txt

        self.time_slider.max = self.data.K-1
        self.step.value = param_copy.step

        self.update_display_channel_list()


    def ui(self):
        '''Create interface'''

        self.interface = ipw.VBox([
            ipw.HTML('<font size="5"><b>Choose main folder<b></font>'),
            ipw.HTML('<font size="2"><b>This folder is either the folder containing the data\
                or the folder containing en existing segmentation to load<b></font>'),
            self.main_folder.file_list,
            self.load_button,
            #ipw.HTML('<br>'),
            ipw.HTML('<br><font size="5"><b>Chose segmentation and signal channels (folders or tifs)<b></font>'),
            ipw.HBox([
                ipw.VBox([ipw.HTML('<font size="2"><b>Segmentation<b></font>'),self.segm_folders]),
                ipw.VBox([ipw.HTML('<font size="2"><b>Signal<b></font>'),self.channels_folders])
            ]),
            self.init_button,
            
            ipw.HTML('<br><font size="5"><b>Set segmentation parameters<b></font>'),
            ipw.VBox([
            self.maxtime,
            self.step,
            self.bad_frames,
            self.segmentation,
            self.diameter,
            self.width_text,
            self.depth_text,
            self.run_button
            ]),
            
            ipw.VBox([self.time_slider, self.intensity_range_slider,
                self.show_windows_choice, self.show_text_choice,
                self.display_channel,
                self.out]),
            
            ipw.HTML('<br><font size="5"><b>Saving<b></font>'),
            ipw.HTML('<font size="2"><b>Select folder where to save<b></font>'),
            self.saving_folder.file_list,
            self.export_button
            
        ])