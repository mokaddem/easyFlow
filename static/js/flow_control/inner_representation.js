function construct_node(moduleName, moduleType, bytes, flowItem, time, cpu_load, memory_load, pid, state, message) {
    var bytes_formated_in = bytes.bytes_in > 0 ? String((parseFloat(bytes.bytes_in)/1000000.0).toFixed(2)) : String(0);
    var bytes_formated_out = bytes.bytes_out > 0 ? String((parseFloat(bytes.bytes_out)/1000000.0).toFixed(2)) : String(0);
    var bytes_formated = bytes_formated_in + ' / ' + bytes_formated_out + ' MB';

    var flowItem_formated_in = flowItem.flowItem_in > 0 ? String(flowItem.flowItem_in) : String(0);
    var flowItem_formated_out = flowItem.flowItem_out > 0 ? String(flowItem.flowItem_out) : String(0);
    var flowItem_formated = flowItem_formated_in + ' / ' + flowItem_formated_out + ' FlowItems';
    var memory_load_formated = (memory_load > 0 ? String((parseFloat(memory_load)/1000000.0).toFixed(2)) : String(0)) + ' MB';

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
    var raw_svg
    switch (moduleType) {
        case 'process':
            raw_svg = raw_process_svg;
            break;
        case 'multiplexer_in':
            raw_svg = raw_multi_in_svg;
            break;
        case 'multiplexer_out':
            raw_svg = raw_multi_out_svg;
            break;
        case 'remote_input':
            raw_svg = raw_remote_in_svg;
                break;
        case 'remote_output':
            raw_svg = raw_remote_out_svg;
            break;
        case 'switch':
            raw_svg = raw_switch_svg;
            break;
        default:
            raw_svg = raw_process_svg;

    }
    var re = new RegExp(Object.keys(mapObj).join("|"),"gi");
    var replaced_svg = raw_svg.replace(re, function(matched){
      return mapObj[matched];
    });
    var url = "data:image/svg+xml;charset=utf-8,"+ encodeURIComponent(replaced_svg);
    return url;
}

function construct_buffer(bufferName, bytes, flowItem) {
    var bytes_formated = (bytes > 0 ? String((parseFloat(bytes)/1000000.0).toFixed(2)) : String(0)) + ' MB';
    var mapObj = {
        '\{\{bufferName\}\}':   bufferName,
        '\{\{bytes\}\}':        bytes_formated,
        '\{\{flowItem\}\}':     flowItem + ' FlowItems'
    };

    var re = new RegExp(Object.keys(mapObj).join("|"),"gi");
    var replaced_svg = raw_buffer_svg.replace(re, function(matched){
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

    }

    set_project(project) {
        this.project.projectName = project.projectName;
        this.project.projectUUID = project.projectUUID;
        this.project.projectInfo = project.projectInfo;
    }

    get_processes_info() {
        $.getJSON( url_get_processes_info, {}, function( data ) {
            innerRepresentation.update_nodes(data.processes, data.buffers);
        });
    }

    update_nodes(processes, buffers) {
        var update_array = [];
        /* Processes */
        try {
            for (var node of processes) {
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
                    size: 75
                });
            }
            this.nodes.update(update_array);
        } catch(err) { /* processes is empty */ }

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
                    size: 30
                });
            }
        } catch(err) { /* processes is empty */ }
        this.nodes.update(update_array);
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
            innerRepresentation.get_processes_info();

        }, auto_refresh_rate);
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
            size: 75
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
                '?',
                '?'
            ),
            x: edgeData.x,
            y: edgeData.y,
            name: edgeData.name,
            type: edgeData.type,
            shape: 'image',
            physics: false,
            mass: 1,
            size: 30
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
                    selectedProcUuid.push(innerRepresentation.processObj[value].puuid)
                    if (index < arr.length-1) { // prevent adding ',' in the end
                        selectedNodesText += innerRepresentation.processObj[value].name+', ';
                    } else {
                        selectedNodesText += innerRepresentation.processObj[value].name;
                    }
                } else if (selectedNodeType == 'buffer') {
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
            var selectedNodeType = innerRepresentation.nodeType(selectedNodes);
            if (selectedNodeType == 'process') {
                node = innerRepresentation.processObj[selectedNodes];
                this.setProcessControlButtonData([node.puuid])
            } else if (selectedNodeType == 'buffer') {
                node = innerRepresentation.bufferObj[selectedNodes];
                this.setBufferControlButtonData([node.buuid])
            } else {
            }
            $('#selectedNodeName').text(node.name);
        }
    }

    setProcessControlButtonData(puuid) {
        $('#pcontrol_play').prop("disabled", false);
        $('#pcontrol_pause').prop("disabled", false);
        $('#pcontrol_restart').prop("disabled", false);
        $('#pcontrol_logs').prop("disabled", false);
        $('#pcontrol_param').prop("disabled", false);
            $('#pcontrol_delete').prop("disabled", false);
            $('#pcontrol_edit').prop("disabled", false);
        flowControl.selected = puuid;
    }

    setBufferControlButtonData(buuid) {
        $('#pcontrol_play').prop("disabled", true);
        $('#pcontrol_pause').prop("disabled", true);
        $('#pcontrol_restart').prop("disabled", true);
        $('#pcontrol_logs').prop("disabled", false);
        $('#pcontrol_param').prop("disabled", false);
            $('#pcontrol_delete').prop("disabled", false);
            $('#pcontrol_edit').prop("disabled", false);
        flowControl.selected = buuid;
    }

    resetControlButtonData() {
        $('#pcontrol_play').prop("disabled", true);
        $('#pcontrol_pause').prop("disabled", true);
        $('#pcontrol_restart').prop("disabled", true);
        $('#pcontrol_logs').prop("disabled", true);
        $('#pcontrol_param').prop("disabled", true);
            $('#pcontrol_delete').prop("disabled", true);
            $('#pcontrol_edit').prop("disabled", true);
        flowControl.selected = [];
    }


}
