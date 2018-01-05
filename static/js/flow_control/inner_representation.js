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
                    from: buffer.fromUUID, to: buffer.toUUID, id: buuid,
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
        if (edgeData.id === undefined) {
            alert('no id');
        }
        if (edgeData.x === undefined || edgeData.y === undefined) {
            var centerCoord = getCenterCoord(edgeData.from, edgeData.to);
            edgeData.x = centerCoord.x;
            edgeData.y = centerCoord.y;
        }
        var i = Math.floor((1 + Math.random()));
        this.bufferObj[edgeData.id] = edgeData.name;
        this.nodes.add({ // add the buffer between the 2 nodes
            id: edgeData.id,
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
            to: edgeData.id,
            arrows: {
                to: {enabled: true, type:'arrow'}
            },
        });
        this.edges.add({
            from: edgeData.id,
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
            this.setControlButtonData(selectedProcUuid);
        } else if (selectedNodes.length == 0){ // no node selected
            $('#selectedNodeName').text("");
            this.setControlButtonData("")
        } else { // one node selected
            var proc = innerRepresentation.processObj[selectedNodes];
            $('#selectedNodeName').text(proc.name);
            this.setControlButtonData([proc.puuid])
        }
    }

    setControlButtonData(puuid) {
        $('#pcontrol_play').data("puuid", puuid)
        $('#pcontrol_pause').data("puuid", puuid)
        $('#pcontrol_param').data("puuid", puuid)
        $('#pcontrol_logs').data("puuid", puuid)
        console.log($('#pcontrol_param').data("puuid"));
    }


}
