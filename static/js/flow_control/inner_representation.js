function construct_node(moduleName, bytes, flowItem, time) {
    // var replaced_svg = raw_module_svg.replace('\{\{moduleName\}\}', moduleName);
    // var replaced_svg = replaced_svg.replace('\{\{bytes\}\}', bytes);
    // var replaced_svg = replaced_svg.replace('\{\{flowItem\}\}', flowItem);
    // var replaced_svg = replaced_svg.replace('\{\{time\}\}', time);
    // var url = "data:image/svg+xml;charset=utf-8,"+ encodeURIComponent(replaced_svg);
    // return url
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
    // var replaced_svg = raw_buffer_svg.replace('\{\{bufferName\}\}', bufferName);
    // var replaced_svg = replaced_svg.replace('\{\{bytes\}\}', bytes);
    // var replaced_svg = replaced_svg.replace('\{\{flowItem\}\}', flowItem);
    // var url = "data:image/svg+xml;charset=utf-8,"+ encodeURIComponent(replaced_svg);
    // return url
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
        this.projectName = getCookie('projectName');
        this.isTempProject = getCookie('isTempProject');
        if (this.isTempProject == 'true') {
            notify('Temporary project:',
            'This project is a temporary project for testing purpose.', 'warning');
        }
        this.nodes = new vis.DataSet();
        this.edges = new vis.DataSet();
        this.processObj = {};
        this.bufferObj = {};
        this.auto_refresh = null;

    }

    get_processes_info() {
        $.getJSON( url_get_processes_info, {}, function( data ) {
            innerRepresentation.update_node(data);
        });
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

    load_network(processes) {
        innerRepresentation.clear();
        this.isTempProject = 'false';
        for (var node of processes) {
            this.addNode(node);
            for (var connection of node.connections) {
                var edgeData = {
                    from: node.id, to: connection.toID, id: connection.BufferID,
                    name: connection.name, x: connection.x, y: connection.y
                };
                this.addBuffer(edgeData);
            }
        }

        if (this.auto_refresh != null) { clearInterval(this.auto_refresh); } // clean up if already running
        this.auto_refresh = setInterval(innerRepresentation.get_processes_info(), auto_refresh_rate);
    }

    update_node(data) {
        var update_array = [];
        for (var node of data) {
            update_array.push({
                id: node['uuid'],
                image: construct_node(
                    node['name'],
                    node['timestamp'],  // bytes
                    node['timestamp'], // flowItem
                    node['timestamp']
                )
            });
        }
        this.nodes.update(update_array);
    }

    addNode(nodeData) {
        this.processObj[nodeData.id] = nodeData.name;
        var  i = parseInt(nodeData.uuid);
        this.nodes.add({
            id: nodeData.uuid,
            image: construct_node(
                nodeData.name,
                String(i*2)+' bytes / ' + String(i*3)+' bytes',
                String(i*5)+' / ' + String(i*4),
                String(i*i*i) + ' sec',
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
}
