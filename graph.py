import matplotlib
matplotlib.use('svg')

from matplotlib import pyplot as plt
from matplotlib.dates import date2num, AutoDateLocator, AutoDateFormatter, DateFormatter

from db_driver import parse_isoformat

from dateutil import tz

import matplotlib.gridspec as gridspec

timezone = tz.gettz('Europe/Sofia')

def handle_graph(db, thing):
    history = db.load_history(thing, 'reported', since_days=1)
    times = list(map(lambda s: parse_isoformat(s['timestamp_utc']), history))
    plot_times = list(map(lambda t: date2num(t), times))
    senses = list(map(lambda s: s['state']['senses'], history))
    modes = list(map(lambda s: s['state']['mode'], history))

    f = plt.figure(figsize=(12, 6), dpi=100)

    gs = gridspec.GridSpec(2, 1, height_ratios=[7,1])

    senses_plot = plt.subplot(gs[0])
    modes_plot = plt.subplot(gs[1], sharex=senses_plot)

    modes_plot.axes.xaxis.set_visible(False)
    
    locator = AutoDateLocator(tz=timezone)
    senses_plot.set_ylabel('senses')
    senses_plot.axes.yaxis.tick_right()
    senses_plot.axes.xaxis.set_major_locator(locator)
    senses_plot.axes.xaxis.set_major_formatter(AutoDateFormatter(locator, tz=timezone))
    modes_plot.set_ylabel('gpio')
    modes_plot.axes.yaxis.tick_right()

    if len(senses) > 0:
        # get keys in the latest senses state, this will result in senses omitted from graph
        # if latest update did not report them
        sense_types = sorted(senses[-1].keys()) 
    else:
        sense_types = []

    for sense_type in sense_types:
        alias = ""
        values = []
        times = []
        for sense_state, time in zip(senses, plot_times):
            if sense_state.get(sense_type) is not None:
                value = sense_state[sense_type]
                if type(value) is dict:
                    values.append(float(value['value']))
                    alias = value['alias']
                else:
                    values.append(float(value))

                times.append(time)

        if alias == "":
            label = sense_type
        else: 
            label = alias

        senses_plot.plot(times, values, label=label)

    if len(modes) > 0:
        mode_types = sorted(modes[-1].keys()) 
    else:
        mode_types = []

    mode_start = 0 
    mode_offset = 2
    labels = []
    yticks = []
    for mode_index, mode_type in enumerate(mode_types):
        alias = ""
        values = []
        times = []
        for mode_state, time in zip(modes, plot_times):
            if mode_state.get(mode_type) is not None:
                value = mode_state[mode_type]
                if type(value) is dict:
                    converted = float(value['value'])
                    alias = value['alias']
                else:
                    converted = float(value)

                if converted == 1:
                    times.append(time)

        if alias == "":
            label = mode_type
        else: 
            label = alias

        y = mode_start + mode_index*mode_offset

        modes_plot.eventplot(times, lineoffsets=y)

        labels.append(label)
        yticks.append(y)

    modes_plot.set_yticks(yticks)
    modes_plot.set_yticklabels(labels)
        
    senses_plot.axes.autoscale()
    senses_plot.grid(True)
    image_location = 'db/%s/graph.png' % thing

    # legend to top of plot, based on example from http://matplotlib.org/users/legend_guide.html
    senses_plot.legend(bbox_to_anchor=(0., 1.02, 1., .102), loc=3,
                       ncol=3, mode="expand", borderaxespad=0.)

    # legend to top of plot, based on example from http://matplotlib.org/users/legend_guide.html
    #senses_plot.legend(bbox_to_anchor=(1, 1),
    #                   ncol=3, bbox_transform = plt.gcf().transFigure)

    plt.savefig(image_location, dpi=100, bbox_inches='tight')

    with open(image_location, 'rb') as f:
        image_bytes = f.read()

    content_type = 'image/png'
    return content_type, image_bytes

