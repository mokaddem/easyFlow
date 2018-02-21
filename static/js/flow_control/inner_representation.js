function construct_node(moduleName, moduleType, bytes, flowItem, time, cpu_load, memory_load, pid, state, message) {
    var bytes_in = bytes.bytes_in > 0 ? parseFloat(bytes.bytes_in) : 0;
    var bytes_out = bytes.bytes_out > 0 ? parseFloat(bytes.bytes_out) : 0;
    var bytes_formated = format_memory(bytes_in) + ' / ' + format_memory(bytes_out);

    var flowItem_formated = format_numbers(flowItem.flowItem_in) + ' / ' + format_numbers(flowItem.flowItem_out) + ' FlowItems';
    var memory_load_formated = (memory_load > 0 ? format_memory(parseFloat(memory_load)) : format_memory(0));

    var state_formated;
    switch (state) {
        case "running":
            state_formated = '#34ce57'
            break;
        case "paused":
            state_formated = '#ffc721'
            break;
        case "crashed":
            state_formated = '#dc3545'
            break;
        default:
            state_formated = '#868e96' // No info
    }
    cpu_load = cpu_load>0 ? cpu_load : 0;
    time = time!='?' ? time : 0;
    var mapObj = {
        '\{\{moduleName\}\}':   moduleName,
        '\{\{bytes\}\}':        bytes_formated,
        '\{\{flowItem\}\}':     flowItem_formated,
        '\{\{time\}\}':         String(parseFloat(time).toFixed(2))+'sec',
        '\{\{cpuload\}\}':      cpu_load+'%',
        '\{\{memload\}\}':      memory_load_formated,
        '\{\{pid\}\}':          pid,
        '\{\{state\}\}':        state_formated,
        '\{\{customMessage\}\}':message
    };
    var raw_svg;
    var simplified_view = $('#switch_simplified_view').prop('checked');
    switch (moduleType) {
        case 'process':
            raw_svg = simplified_view ? raw_process_svg_simplified : raw_process_svg;
            break;
        case 'multiplexer_in':
            raw_svg = simplified_view ? raw_multi_in_svg_simplified : raw_multi_in_svg;
            break;
        case 'multiplexer_out':
            raw_svg = simplified_view ? raw_multi_out_svg_simplified : raw_multi_out_svg;
            break;
        case 'remote_input':
            raw_svg = simplified_view ? raw_remote_in_svg_simplified : raw_remote_in_svg;
            break;
        case 'remote_output':
            raw_svg = simplified_view ? raw_remote_out_svg_simplified : raw_remote_out_svg;
            break;
        case 'switch':
            raw_svg = simplified_view ? raw_switch_svg_simplified : raw_switch_svg;
            break;
        default:
            raw_svg = simplified_view ? raw_process_svg_simplified : raw_process_svg;
    }
    var re = new RegExp(Object.keys(mapObj).join("|"),"gi");
    var replaced_svg = raw_svg.replace(re, function(matched){
      return mapObj[matched];
    });
    var url = "data:image/svg+xml;charset=utf-8,"+ encodeURIComponent(replaced_svg);
    return url;
}

function construct_buffer(bufferName, bytes, flowItem) {
    var simplified_view = $('#switch_simplified_view').prop('checked');
    var bytes_formated = (bytes > 0 ? format_memory(parseFloat(bytes)) : format_memory(0));
    var flowItem_formated = parseFloat(flowItem) == NaN ? 0 : format_numbers(flowItem);
    var mapObj = {
        '\{\{bufferName\}\}':   bufferName,
        '\{\{bytes\}\}':        bytes_formated,
        '\{\{flowItem\}\}':     flowItem_formated + ' FlowItems'
    };

    var re = new RegExp(Object.keys(mapObj).join("|"),"gi");
    var replaced_svg = (simplified_view ? raw_buffer_svg_simplified : raw_buffer_svg).replace(re, function(matched){
      return mapObj[matched];
    });
    var url = "data:image/svg+xml;charset=utf-8,"+ encodeURIComponent(replaced_svg);
    return url;
}

function getCenterCoord(fromID, toID) {
    var pos = network.getPositions([fromID, toID]);
    var centerX = pos[fromID].x + (pos[toID].x - pos[fromID].x)/2;
    var centerY = pos[fromID].y + (pos[toID].y - pos[fromID].y)/2;
    return {x: centerX, y: centerY};
}

class InnerRepresentation {
    constructor() {
        this.project = {
            projectName: getCookie('projectName'),
            projectUUID: getCookie('projectUUID'),
            projectInfo: getCookie('projectInfo')
        }

        this.nodes = new vis.DataSet();
        this.edges = new vis.DataSet();
        this.processObj = {};
        this.bufferObj = {};
        this.auto_refresh = null;
        this.selection_box = {};
        this.in_selection = false;
        this.system_stats = {
            cpu_load: new timed_sliding_array(30),
            memory_load: new timed_sliding_array(30),
            buffered_item: new timed_sliding_array(30),
            buffered_bytes: new timed_sliding_array(30)
        };
    }

    set_project(project) {
        this.project.projectName = project.projectName;
        this.project.projectUUID = project.projectUUID;
        this.project.projectInfo = project.projectInfo;
    }

    isProjectOpen() {
        return this.project.projectUUID !== undefined;
    }

    get_processes_info() {
        $.getJSON( url_get_processes_info, {}, function( data ) {
            innerRepresentation.update_nodes(data.processes, data.buffers);
        });
    }

    /* SELECTION BOX */
    reset_selection_box() {
        this.selection_box = {};
        this.in_selection = false;
    }
    set_selection_box(x1, y1, x2, y2) {
        this.in_selection = true;
        var start_coord = network.DOMtoCanvas({x: x1, y: y1});
        var end_coord = network.DOMtoCanvas({x: x2, y: y2});
        if (start_coord.x <= end_coord.x) {
            this.selection_box.start_x = start_coord.x;
            this.selection_box.end_x = end_coord.x;
        } else { // reverse box (canvas centered in middle of screen)
            this.selection_box.start_x = end_coord.x;
            this.selection_box.end_x = start_coord.x;
        }
        if (start_coord.y <= end_coord.y) {
            this.selection_box.start_y = start_coord.y;
            this.selection_box.end_y = end_coord.y;
        } else {
            this.selection_box.start_y = end_coord.y;
            this.selection_box.end_y = start_coord.y;
        }
    }
    handle_selection_box() {
        if ( this.selection_box != {} ) {
            this.selectNodesFromRectangle(this.selection_box);
        }
        this.reset_selection_box();
    }


    selectNodesFromRectangle(selection_box) {
        var nodesIdInDrawing = network.getSelectedNodes();
        var process_only = $('#switch_select_process_only').prop('checked');

        var allNodesPos = network.getPositions(); // get all nodes
        allNodesPos = objectToArray(allNodesPos);
        for (var i = 0; i < allNodesPos.length; i++) {
            var curNode = allNodesPos[i];
            if (selection_box.start_x <= curNode.x && curNode.x <= selection_box.end_x &&
                selection_box.start_y <= curNode.y && curNode.y <= selection_box.end_y)
            {
                if (process_only) {
                    if (this.nodeType(curNode.id) != 'buffer'){
                        nodesIdInDrawing.push(curNode.id);
                    }
                } else {
                    nodesIdInDrawing.push(curNode.id);
                }
            }
        }
        network.selectNodes(nodesIdInDrawing);
        this.handleNodeSelection({nodes: nodesIdInDrawing})
    }

    update_sparkline_control(jStats) {
        if (jStats === undefined) {
            var sparklineBI = $('.inlinesparklineBI').sparkline([],{width: '40%', height: '35px', chartRangeMin: 0,
                tooltipFormatter: function (sparkline, options, fields) {
                    return "" + sparklineDateFormatter(fields.x) + " - " + sparklineMbFormatter(fields.y) + "";
                }
            });
            var sparklineBO = $('.inlinesparklineBO').sparkline([],{width: '40%', height: '35px', chartRangeMin: 0,
                tooltipFormatter: function (sparkline, options, fields) {
                    return "" + sparklineDateFormatter(fields.x) + " - " + sparklineMbFormatter(fields.y) + "";
                }
            });
            var sparklineFI = $('.inlinesparklineFI').sparkline([],{width: '40%', height: '35px', chartRangeMin: 0,
                tooltipFormatter: function (sparkline, options, fields) {
                    return "" + sparklineDateFormatter(fields.x) + " - " + fields.y + "";
                }
            });
            var sparklineFO = $('.inlinesparklineFO').sparkline([],{width: '40%', height: '35px', chartRangeMin: 0,
                tooltipFormatter: function (sparkline, options, fields) {
                    return "" + sparklineDateFormatter(fields.x) + " - " + fields.y + "";
                }
            });

            var sparklineBI_speed = $('.inlinesparklineBI_speed').sparkline([],{width: '40%', height: '35px', chartRangeMin: 0,
                tooltipFormatter: function (sparkline, options, fields) {
                    return "" + sparklineDateFormatter(fields.x) + " - " + sparklineMbFormatter(fields.y) + "";
                }
            });
            var sparklineBO_speed = $('.inlinesparklineBO_speed').sparkline([],{width: '40%', height: '35px', chartRangeMin: 0,
                tooltipFormatter: function (sparkline, options, fields) {
                    return "" + sparklineDateFormatter(fields.x) + " - " + sparklineMbFormatter(fields.y) + "";
                }
            });
            var sparklineFI_speed = $('.inlinesparklineFI_speed').sparkline([],{width: '40%', height: '35px', chartRangeMin: 0,
                tooltipFormatter: function (sparkline, options, fields) {
                    return "" + sparklineDateFormatter(fields.x) + " - " + fields.y + "";
                }
            });
            var sparklineFO_speed = $('.inlinesparklineFO_speed').sparkline([],{width: '40%', height: '35px', chartRangeMin: 0,
                tooltipFormatter: function (sparkline, options, fields) {
                    return "" + sparklineDateFormatter(fields.x) + " - " + fields.y + "";
                }
            });
        } else {
            var sparklineBI = $('.inlinesparklineBI').sparkline(jStats['bytes_in_history'],{width: '40%', height: '35px', chartRangeMin: 0,
                tooltipFormatter: function (sparkline, options, fields) {
                    return "" + sparklineDateFormatter(fields.x) + " - " + format_memory(fields.y) + "";
                }
            });
            // $('#inlinesparklineBI_max').text();
            var sparklineBO = $('.inlinesparklineBO').sparkline(jStats['bytes_out_history'],{width: '40%', height: '35px', chartRangeMin: 0,
                tooltipFormatter: function (sparkline, options, fields) {
                    return "" + sparklineDateFormatter(fields.x) + " - " + format_memory(fields.y) + "";
                }
            });
            var sparklineFI = $('.inlinesparklineFI').sparkline(jStats['flowItem_in_history'],{width: '40%', height: '35px', chartRangeMin: 0,
                tooltipFormatter: function (sparkline, options, fields) {
                    return "" + sparklineDateFormatter(fields.x) + " - " + format_numbers(fields.y) + "";
                }
            });
            var sparklineFO = $('.inlinesparklineFO').sparkline(jStats['flowItem_out_history'],{width: '40%', height: '35px', chartRangeMin: 0,
                tooltipFormatter: function (sparkline, options, fields) {
                    return "" + sparklineDateFormatter(fields.x) + " - " + format_numbers(fields.y) + "";
                }
            });

            var sparklineBI_speed = $('.inlinesparklineBI_speed').sparkline(jStats['bytes_in_speed'],{width: '40%', height: '35px', chartRangeMin: 0,
                tooltipFormatter: function (sparkline, options, fields) {
                    return "" + sparklineDateFormatter(fields.x) + " - " + format_memory(fields.y) + "";
                }
            });
            var sparklineBO_speed = $('.inlinesparklineBO_speed').sparkline(jStats['bytes_out_speed'],{width: '40%', height: '35px', chartRangeMin: 0,
                tooltipFormatter: function (sparkline, options, fields) {
                    return "" + sparklineDateFormatter(fields.x) + " - " + format_memory(fields.y) + "";
                }
            });
            var sparklineFI_speed = $('.inlinesparklineFI_speed').sparkline(jStats['flowItem_in_speed'],{width: '40%', height: '35px', chartRangeMin: 0,
                tooltipFormatter: function (sparkline, options, fields) {
                    return "" + sparklineDateFormatter(fields.x) + " - " + format_numbers(fields.y) + "";
                }
            });
            var sparklineFO_speed = $('.inlinesparklineFO_speed').sparkline(jStats['flowItem_out_speed'],{width: '40%', height: '35px', chartRangeMin: 0,
                tooltipFormatter: function (sparkline, options, fields) {
                    return "" + sparklineDateFormatter(fields.x) + " - " + format_numbers(fields.y) + "";
                }
            });
        }
    }

    update_sparkline_stats() {
        var sparkline_system_load = $('#process_cpu_load_spark').sparkline(this.system_stats.cpu_load.get(),{width: '150px', height: '35px', chartRangeMin: 0, chartRangeMax: max_cpu_load,
            tooltipFormatter: function (sparkline, options, fields) {
                return "" + sparklineDateFormatter(fields.x) + " - " + format_numbers(fields.y) + " %";
            }
        });
        var sparkline_memory_load = $('#process_memory_load_spark').sparkline(this.system_stats.memory_load.get(),{width: '150px', height: '35px', chartRangeMin: 0, chartRangeMax: max_memory_load,
        tooltipFormatter: function (sparkline, options, fields) {
            return "" + sparklineDateFormatter(fields.x) + " - " + format_memory(fields.y) + "";
        }
        });
        var sparkline_buffered_item = $('#buffered_item_spark').sparkline(this.system_stats.buffered_item.get(),{width: '150px', height: '35px', chartRangeMin: 0, chartRangeMax: this.system_stats.buffered_item.getMax(),
            tooltipFormatter: function (sparkline, options, fields) {
                return "" + sparklineDateFormatter(fields.x) + " - " + format_numbers(fields.y) + "";
            }
        });
        $('#stats_pannel_buffered_items_max').text(format_numbers(this.system_stats.buffered_item.getMax()));
        var sparkline_buffered_bytes = $('#buffered_bytes_spark').sparkline(this.system_stats.buffered_bytes.get(),{width: '150px', height: '35px', chartRangeMin: 0, chartRangeMax: this.system_stats.buffered_bytes.getMax(),
            tooltipFormatter: function (sparkline, options, fields) {
                return "" + sparklineDateFormatter(fields.x) + " - " + format_memory(fields.y) + "";
            }
        });
        $('#stats_pannel_buffered_bytes_max').text(format_memory(this.system_stats.buffered_bytes.getMax()));
    }

    update_nodes(processes, buffers) {
        var update_array = [];
        var sum_cpu_load = 0;
        var sum_memory_load = 0;
        var sum_buffered_item = 0;
        var sum_buffered_bytes = 0;
        /* Processes */
        try {
            if (processes.length == 0) {
                this.clean_control_table();
                this.update_sparkline_control();
            }
            for (var node of processes) {
                if (jQuery.isEmptyObject(node)) {
                    continue;
                }
                var jStats = node['stats'];
                update_array.push({
                    id: node['puuid'],
                    image: construct_node(
                        node['name'],
                        node['type'],
                        { bytes_in: jStats['bytes_in'], bytes_out: jStats['bytes_out'] },  // bytes
                        { flowItem_in: jStats['flowItem_in'], flowItem_out: jStats['flowItem_out'] }, // flowItem
                        jStats['processing_time'],
                        jStats['cpu_load'],
                        jStats['memory_load'],
                        jStats['pid'],
                        jStats['state'],
                        jStats['custom_message']

                    ),
                    size: get_node_size_from_type(node['type'])
                });
                sum_cpu_load += jStats['cpu_load']*2
                sum_memory_load += jStats['memory_load']
                // update table in control panel
                if (flowControl.selected.length > 0 && node['puuid'] == flowControl.selected[0]) {
                    var formatted_data = format_proc_data(
                        node['name'],
                        node['puuid'],
                        node['type'],
                        { bytes_in: jStats['bytes_in'], bytes_out: jStats['bytes_out'] },
                        { flowItem_in: jStats['flowItem_in'], flowItem_out: jStats['flowItem_out'] },
                        jStats['processing_time'],
                        jStats['cpu_load'],
                        jStats['memory_load'],
                        jStats['pid'],
                        jStats['state'],
                        jStats['custom_message'])
                    this.update_control_table(formatted_data);
                    this.update_sparkline_control(jStats);
                }
            }
            this.nodes.update(update_array);
            this.system_stats.cpu_load.add(sum_cpu_load);
            this.system_stats.memory_load.add(sum_memory_load);
        } catch(err) { /* processes is empty or don't have all the fields */
            this.clean_control_table();
            this.update_sparkline_control();
        }

        /* Buffers */
        try {
            for (var node of buffers) {
                var jStats = node['stats'];
                update_array.push({
                    id: node['buuid'],
                    image: construct_buffer(
                        node['name'],
                        jStats['buffered_bytes'],  // bytes
                        jStats['buffered_flowItems']
                    ),
                    size: get_node_size_from_type('buffer')
                });
                sum_buffered_item += jStats['buffered_flowItems'];
                sum_buffered_bytes += jStats['buffered_bytes'];
            }
        } catch(err) { /* processes is empty */ }
        this.nodes.update(update_array);
        this.system_stats.buffered_item.add(sum_buffered_item);
        this.system_stats.buffered_bytes.add(sum_buffered_bytes);
        this.update_sparkline_stats();
    }

    nodeType(nodeID) {
        if (innerRepresentation.processObj[nodeID] != undefined) {
            return 'process';
        } else if (innerRepresentation.bufferObj[nodeID] != undefined) {
            return 'buffer';
        } else {
            return 'unknown';
        }
    }

    clear() {
        this.nodes.clear();
        this.edges.clear();
    }

    load_network(data) {
        var processes = data.processes;
        innerRepresentation.clear();
        for (var puuid in processes) {
            if (processes.hasOwnProperty(puuid)) {
                var node = processes[puuid];
                node.puuid = puuid;
                this.addNode(node);
            }
        }
        var buffers = data.buffers;
        for (var buuid in buffers) {
            if (buffers.hasOwnProperty(buuid)) {
                var buffer = buffers[buuid];
                var edgeData = {
                    from: buffer.fromUUID, to: buffer.toUUID, buuid: buuid,
                    name: buffer.name, x: buffer.x, y: buffer.y
                };
            }
            this.addBuffer(edgeData);
        }
        if (this.auto_refresh != null) { clearInterval(this.auto_refresh); } // clean up if already running

        this.auto_refresh = setInterval( function() {
            if (!innerRepresentation.in_selection) { // do not update nodes if we are in selection
                innerRepresentation.get_processes_info();
            }
        }, auto_refresh_rate*1000);
    }

    resync_representation(callback_resync) {
        toggle_loading(true);
        $.getJSON( url_load_network, {projectUUID: this.project.projectUUID}, function( data ) {
            $('#projectName').text(data.projectName);
            $('#projectName').append('<small>'+data.projectInfo+'</small>');
            innerRepresentation.load_network(data);
            toggle_loading(false);
            if (callback_resync != undefined) {
                callback_resync();
            }
        });
    }

    addNode(nodeData) {
        this.processObj[nodeData.puuid] = nodeData;
        this.nodes.add({
            id: nodeData.puuid,
            image: construct_node(
                nodeData.name,
                nodeData.type,
                '?',
                '?',
                '?',
                '?',
                '?',
                '?',
                '?',
                ''
            ),
            x: nodeData.x,
            y: nodeData.y,
            name: nodeData.name,
            type: nodeData.type,
            shape: 'image',
            physics: false,
            mass: 3,
            size: get_node_size_from_type(nodeData.type)
        });
    }

    // edgeData = {from: nodeID, to: nodeID}
    addEdge(edgeData) {
        this.edges.add({
            from: edgeData.from,
            to: edgeData.to,
            arrows: {
                to: {enabled: true, type:'arrow'}
            },
        });
    }

    addBuffer(edgeData) {
        var btnPipe = $('button[name="pipe"]');
        if (edgeData.buuid === undefined) {
            alert('no id');
        }
        if (edgeData.x === undefined || edgeData.y === undefined) {
            var centerCoord = getCenterCoord(edgeData.from, edgeData.to);
            edgeData.x = centerCoord.x;
            edgeData.y = centerCoord.y;
        }
        var i = Math.floor((1 + Math.random()));
        this.bufferObj[edgeData.buuid] = edgeData;
        this.nodes.add({ // add the buffer between the 2 nodes
            id: edgeData.buuid,
            image: construct_buffer(
                edgeData.name,
                0,
                0
            ),
            x: edgeData.x,
            y: edgeData.y,
            name: edgeData.name,
            type: edgeData.type,
            shape: 'image',
            physics: false,
            mass: 1,
            size: get_node_size_from_type('buffer')
        });
        this.edges.add({ // link nodes to buffer
            from: edgeData.from,
            to: edgeData.buuid,
            arrows: {
                to: {enabled: true, type:'arrow'}
            },
        });
        this.edges.add({
            from: edgeData.buuid,
            to: edgeData.to,
            arrows: {
                to: {enabled: true, type:'arrow'}
            },
        });
        btnPipe.attr('activated', 'false');
        toggle_btn_pipe(false);
    }

    clear_selection() {
        this.handleNodeSelection({nodes: []})
    }

    update_control_table(data) {
        $('#selectedType').text(data.type);
        $('#selectedUUID').text(data.uuid);
        $('#selectedState').text(data.state);
        $('#selectedByte').text(data.bytes);
        $('#selectedFlowItem').text(data.flowItems);
        $('#selectedTime').text(data.time);
        $('#selectedCPULoad').text(data.cpuload);
        $('#selectedMemoryLoad').text(data.memload);
        $('#selectedPID').text(data.pid);
        $('#selectedMessage').text(data.customMessage);
    }

    clean_control_table() {
        $('#selectedType').text('');
        $('#selectedUUID').text('');
        $('#selectedState').text('Not running or Unkwown');
        $('#selectedByte').text('');
        $('#selectedFlowItem').text('');
        $('#selectedTime').text('');
        $('#selectedCPULoad').text('');
        $('#selectedMemoryLoad').text('');
        $('#selectedPID').text('?');
        $('#selectedMessage').text('This process is most likely not running');
    }

    handleNodeSelection(params) {
        var selectedNodes = params.nodes;
        if(selectedNodes.length > 1) { // multiple node selected
            var selectedNodesText = "";
            var selectedNodeType;
            var selectedObjType;
            var selectedProcUuid = [];
            selectedNodes.map(function(value, index, arr) {
                if (index == 0) {  // check if same node type
                    selectedNodeType = innerRepresentation.nodeType(value);
                }

                if (innerRepresentation.nodeType(value) != selectedNodeType) { // not same type of node
                    return false; // skip
                }

                if (selectedNodeType == 'process') {
                    selectedProcUuid.push(innerRepresentation.processObj[value].puuid);
                    if (index < arr.length-1) { // prevent adding ',' in the end
                        selectedNodesText += innerRepresentation.processObj[value].name+', ';
                    } else {
                        selectedNodesText += innerRepresentation.processObj[value].name;
                    }
                } else if (selectedNodeType == 'buffer') {
                    selectedProcUuid.push(innerRepresentation.bufferObj[value].buuid);
                    if (index < arr.length-1) { // prevent adding ',' in the end
                        selectedNodesText += innerRepresentation.bufferObj[value].name+', ';
                    } else {
                        selectedNodesText += innerRepresentation.bufferObj[value].name;
                    }
                } else {
                    console.log('unknown selectedNodeType');
                }


            });
            $('#selectedNodeName').text(selectedNodesText);
            if (selectedNodeType == 'process') { // is process
                this.setProcessControlButtonData(selectedProcUuid);
            } else if (selectedNodeType == 'buffer') {
                this.setBufferControlButtonData(selectedProcUuid);
            }
        } else if (selectedNodes.length == 0){ // no node selected
            $('#selectedNodeName').text("");
            this.resetControlButtonData();
        } else { // one node selected
            var node;
            if (selectedNodes.length == 1) { // in case of list
                selectedNodes = selectedNodes[0];
            }
            var selectedNodeType = innerRepresentation.nodeType(selectedNodes);
            if (selectedNodeType == 'process') {
                node = innerRepresentation.processObj[selectedNodes];
                this.setProcessControlButtonData([node.puuid]);
            } else if (selectedNodeType == 'buffer') {
                node = innerRepresentation.bufferObj[selectedNodes];
                this.setBufferControlButtonData([node.buuid]);
            } else {
            }
            $('#selectedNodeName').text(node.name);
        }
    }

    setProcessControlButtonData(puuid) {
        $('#pcontrol_play').prop("disabled", false);
        $('#pcontrol_pause').prop("disabled", false);
        $('#pcontrol_stop').prop("disabled", false);
        $('#pcontrol_restart').prop("disabled", false);
        $('#pcontrol_clone').prop("disabled", false);
        $( "#pcontrol_empty" ).hide(0);
        $('#pcontrol_logs').prop("disabled", false);
        $('#pcontrol_param').prop("disabled", false);
            $('#pcontrol_delete').prop("disabled", false);
            $('#pcontrol_edit').prop("disabled", false);
        flowControl.selected = puuid;
        $('#controlPanelCollapse').collapse('show');
        $('#controlPanel').toggleClass('panel-info', false);
        $('#controlPanel').toggleClass('panel-primary', true);
    }

    setBufferControlButtonData(buuid) {
        $('#pcontrol_play').prop("disabled", true);
        $('#pcontrol_pause').prop("disabled", true);
        $('#pcontrol_stop').prop("disabled", true);
        $('#pcontrol_restart').prop("disabled", true);
        $('#pcontrol_clone').prop("disabled", true);
        $( "#pcontrol_empty" ).show(0);
        $('#pcontrol_logs').prop("disabled", false);
        $('#pcontrol_param').prop("disabled", false);
            $('#pcontrol_delete').prop("disabled", false);
            $('#pcontrol_edit').prop("disabled", false);
        flowControl.selected = buuid;
        $('#controlPanelCollapse').collapse('hide');
        $('#controlPanel').toggleClass('panel-info', false);
        $('#controlPanel').toggleClass('panel-primary', true);
        // $('#selectedNodeID').text(buuid);
    }

    resetControlButtonData() {
        $('#pcontrol_play').prop("disabled", true);
        $('#pcontrol_pause').prop("disabled", true);
        $('#pcontrol_stop').prop("disabled", true);
        $('#pcontrol_restart').prop("disabled", true);
        $('#pcontrol_clone').prop("disabled", true);
        $( "#pcontrol_empty" ).hide(0);
        $('#pcontrol_logs').prop("disabled", true);
        $('#pcontrol_param').prop("disabled", true);
            $('#pcontrol_delete').prop("disabled", true);
            $('#pcontrol_edit').prop("disabled", true);
        flowControl.selected = [];
        $('#controlPanelCollapse').collapse('hide');
        $('#controlPanel').toggleClass('panel-info', true);
        $('#controlPanel').toggleClass('panel-primary', false);
    }

    show_log(pName, puuid) {
        $('#modalShowLogTitle').text("Log of: "+pName);
        $('#'+'modalShowLog').modal('show');
        $('#'+'modalShowLog').one('hidden.bs.modal', function (e) {
            if (realtimeLogs !== null) {
                // close realtime log
                realtimeLogs.close_listener();
                $('#switch_show_realtime_log').prop('checked', false);
                realtimeLogs = null;
            }
        })
        if (logListDatatable == null) {
            logListDatatable = $('#logTable').DataTable( {
                "order": [[ 1, "desc" ]],
                "ajax": {
                    "url": url_get_log+"?puuid="+puuid,
                    "dataSrc": ""
                },
                "fnRowCallback": function( nRow, aData, iDisplayIndex, iDisplayIndexFull ) {
                    // nRow.classList.add('success')
                    switch (aData.log_level) {
                        case 'DEBUG':
                            // setTimeout(function() {
                            //     nRow.classList.remove('success');
                            // }, 700);
                            break;
                        case 'INFO':
                            // setTimeout(function() {
                            //     nRow.classList.remove('success');
                                nRow.classList.add('info');
                            // }, 700);
                            break;
                        case 'WARNING':
                            // setTimeout(function() {
                            //     nRow.classList.remove('success');
                                nRow.classList.add('warning')
                            // }, 700);
                            break;
                        case 'ERROR':
                            // setTimeout(function() {
                            //     nRow.classList.remove('success');
                                nRow.classList.add('danger')
                            // }, 700);
                            break;
                        case 'NONE':
                            break;
                        default:

                    }
                },
                "columns": [
                    { data: "log_level" },
                    {
                        data: "time",
                        render: function(data, type, row) {
                            var d = new Date(parseInt(data)*1000);
                            return type === "display" || type === "filter" ?
                                d.toLocaleString() : d;
                        }
                    },
                    { data: "message" },
                ]
            });
        } else {
            logListDatatable.ajax.reload();
        }
        this.applyLogLevelFiltering();
    }

    applyLogLevelFiltering() {
        // generate the regex to filter logs in datatable
        var log_levels_regex = '(' + $("#checkboxes_log_level").find("input:checked").map(function() {
                return this.value
        }).get().join('|') + ')';
        logListDatatable // filter rows based on checked log level
            .columns( 0 )
            .search( log_levels_regex, true )
            .draw();
    }


}
