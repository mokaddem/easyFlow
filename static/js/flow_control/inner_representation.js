function construct_node(moduleName, bytes, flowItem, time) {
    var mapObj = {
        '\{\{moduleName\}\}':   moduleName,
        '\{\{bytes\}\}':        bytes,
        '\{\{flowItem\}\}':     flowItem,
        '\{\{time\}\}':         time
    };

    var re = new RegExp(Object.keys(mapObj).join("|"),"gi");
    var replaced_svg = raw_module_svg.replace(re, function(matched){
      return mapObj[matched];
    });
    var url = "data:image/svg+xml;charset=utf-8,"+ encodeURIComponent(replaced_svg);
    return url;
}

function construct_buffer(bufferName, bytes, flowItem) {
    var mapObj = {
        '\{\{bufferName\}\}':   bufferName,
        '\{\{bytes\}\}':        bytes,
        '\{\{flowItem\}\}':     flowItem
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
            innerRepresentation.update_nodes(data.processes);
        });
    }

    update_nodes(processes) {
        var update_array = [];
        try {
            for (var node of processes) {
                update_array.push({
                    id: node['puuid'],
                    image: construct_node(
                        node['name'],
                        node['timestamp'],  // bytes
                        node['timestamp'], // flowItem
                        node['timestamp']
                    )
                });
            }
            this.nodes.update(update_array);
        } catch(err) { /* processes is empty */ }
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
        var  i = parseInt(nodeData.puuid);
        this.nodes.add({
            id: nodeData.puuid,
            image: construct_node(
                nodeData.name,
                '?',
                '?',
                '?',
            ),
            x: nodeData.x,
            y: nodeData.y,
            shape: 'image',
            physics: false,
            mass: 3
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
                String(i*2)+' bytes / ' + String(i*3)+' bytes',
                String(i*5)+' / ' + String(i*4),
            ),
            x: edgeData.x,
            y: edgeData.y,
            shape: 'image',
            physics: false,
            mass: 1,
            size: 15
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

    handleNodeSelection(params) {
        var selectedNodes = params.nodes;
        if(selectedNodes.length > 1) { // multiple node selected
            var selectedNodesText = "";
            var selectedNodeType;
            var selectedProcUuid = [];
            selectedNodes.map(function(value, index, arr) {
                if (index == 0) {  // check if same node type
                    selectedNodeType = innerRepresentation.nodeType(value);
                }

                if (innerRepresentation.nodeType(value) != selectedNodeType) { // not same type of node
                    return false; // skip
                }
                selectedProcUuid.push(innerRepresentation.processObj[value].puuid)
                if (index < arr.length-1) { // prevent adding ',' in the end
                    selectedNodesText += innerRepresentation.processObj[value].name+', ';
                } else {
                    selectedNodesText += innerRepresentation.processObj[value].name;
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
        $('#pcontrol_param').prop("disabled", false);
        $('#pcontrol_delete').prop("disabled", false);
        $('#pcontrol_logs').prop("disabled", false);
        flowControl.selected = puuid;
    }

    setBufferControlButtonData(buuid) {
        $('#pcontrol_play').prop("disabled", true);
        $('#pcontrol_pause').prop("disabled", true);
        $('#pcontrol_param').prop("disabled", false);
        $('#pcontrol_delete').prop("disabled", false);
        $('#pcontrol_logs').prop("disabled", false);
        flowControl.selected = buuid;
    }

    resetControlButtonData() {
        $('#pcontrol_play').prop("disabled", true);
        $('#pcontrol_pause').prop("disabled", true);
        $('#pcontrol_param').prop("disabled", true);
        $('#pcontrol_delete').prop("disabled", true);
        $('#pcontrol_logs').prop("disabled", true);
        flowControl.selected = [];
    }


}
