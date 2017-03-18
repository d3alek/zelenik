import matplotlib
matplotlib.use('svg')

from matplotlib import pyplot as plt
from matplotlib.dates import date2num, AutoDateLocator, AutoDateFormatter, DateFormatter

from db_driver import parse_isoformat

from dateutil import tz

import matplotlib.gridspec as gridspec

timezone = tz.gettz('Europe/Sofia')

def get_write(state):
    if state.get('write'):
        return state['write']
    elif state.get('mode'):
        return state['mode']
    else:
        return {}

def get_senses(state):
    if state.get('senses'):
        return state['senses']
    else:
        return {}

def handle_graph(db, thing):
    history = db.load_history(thing, 'reported', since_days=1)
    times = list(map(lambda s: parse_isoformat(s['timestamp_utc']), history))
    plot_times = list(map(lambda t: date2num(t), times))
    senses = list(map(lambda s: get_senses(s['state']), history))
    writes = list(map(lambda s: get_write(s['state']), history))

    f = plt.figure(figsize=(12, 6), dpi=100)

    gs = gridspec.GridSpec(2, 1, height_ratios=[7,1])

    senses_plot = plt.subplot(gs[0])
    writes_plot = plt.subplot(gs[1], sharex=senses_plot)

    writes_plot.axes.xaxis.set_visible(False)
    
    locator = AutoDateLocator(tz=timezone)
    senses_plot.set_ylabel('senses')
    senses_plot.axes.yaxis.tick_right()
    senses_plot.axes.xaxis.set_major_locator(locator)
    senses_plot.axes.xaxis.set_major_formatter(AutoDateFormatter(locator, tz=timezone))
    writes_plot.set_ylabel('gpio')
    writes_plot.axes.yaxis.tick_right()

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

    if len(writes) > 0:
        writes_types = sorted(writes[-1].keys()) 
    else:
        writes_types = []

    writes_start = 0 
    writes_offset = -2
    labels = []
    yticks = []
    for writes_index, writes_type in enumerate(writes_types):
        alias = ""
        values = []
        intervals = []
        interval = None
        times = []
        
        for writes_state, time in zip(writes, plot_times):
            if writes_state.get(writes_type) is not None:
                value = writes_state[writes_type]
                if type(value) is dict:
                    converted = float(value['value'])
                    alias = value['alias']
                else:
                    converted = int(value)

                if converted == 1:
                    if not interval:
                        interval = (time, 0.0001) # about 1 minute
                    else:
                        interval = (interval[0], time-interval[0])
                else:
                    if interval:
                        interval = (interval[0], time-interval[0])
                        intervals.append(interval)
                        interval = None

        if interval:
            intervals.append(interval)

        if alias == "":
            label = writes_type
        else: 
            label = alias

        y = writes_start + writes_index*writes_offset

        writes_plot.broken_barh(intervals, (y+0.5, writes_offset+0.5)) # -0.5 to center on named y axis

        labels.append(label)
        yticks.append(y)

    writes_plot.set_yticks(yticks)
    writes_plot.set_yticklabels(labels)
        
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

