class FlowControl {
    constructor() {
        this.selected = [];
    }

    delete_node() {
        var uuids = this.selected;
        if (innerRepresentation.nodeType(uuids[0]) == 'process') { // uuids are the same type
            this.execute_operation('delete_process', {puuid: uuids}, false);
        } else if ((innerRepresentation.nodeType(uuids[0]) == 'buffer')) { // uuids are the same type
            this.execute_operation('delete_link', {buuid: uuids}, false);
        } else {
        }
        // reset selection
        this.selected = [];
        innerRepresentation.clear_selection();
    }

    pause_node() {
        var uuids = this.selected;
        this.execute_operation('pause_process', {puuid: uuids}, false);
    }
    play_node() {
        var uuids = this.selected;
        this.execute_operation('play_process', {puuid: uuids}, false);
    }
    stop_node() {
        var uuids = this.selected;
        this.execute_operation('stop_process', {puuid: uuids}, false);
    }
    empty_buffer() {
        var uuids = this.selected;
        if (confirm("Confirm: Empty selected buffer(s)")) {
            this.execute_operation('empty_buffer', {buuid: uuids}, false);
        }
    }
    get_logs() {
        if (this.selected.length > 0) {
            var uuid = this.selected[0];
            innerRepresentation.show_log(innerRepresentation.nodes.get(uuid).name, uuid);
        }
    }
    restart_node() {
        var uuids = this.selected;
        this.execute_operation('restart_process', {puuid: uuids}, false);
    }
    duplicate_selected() {
        // need to query ids from the network as the selection handler only takes nodes from the same type
        var node_ids = network.getSelection().nodes;
        this.execute_operation('clone', {uuids: node_ids}, false);
    }

    edit_node() {
        var self = this;
        if (this.selected.length > 1) { return; /* do not edit if multiple nodes are selected */ }
        var uuid = this.selected[0];
        if (innerRepresentation.nodeType(uuid) == 'process') {
            var processType = innerRepresentation.processObj[uuid].type;
            var modalType = getModalTypeFromProcessType(processType);
            this.query_config_and_fill_form(uuid, modalType, {type: 'process', uuid: uuid}, function() {
                var modalID = 'modal'+modalType;
                $('#'+modalID).modal('show');
                self.handleModalConfirm(modalType, { type: "process", puuid: uuid, update: true}, function(modalData) {
                    console.log(modalData);
                    self.execute_operation('edit_process', modalData)
                    .done(function(responseData, textStatus, jqXHR) {
                    })
                    .fail(function() {
                        console.log( "An error occured" );
                    });
                });

            });
        } else if (innerRepresentation.nodeType(uuid) == 'buffer') {
            var modalType = 'AddLink'
            this.query_config_and_fill_form(uuid, modalType, {type: 'buffer', uuid: uuid}, function() {
                var modalID = 'modal'+modalType;
                $('#'+modalID).modal('show');
                self.handleModalConfirm('AddLink', {type: 'buffer', buuid: uuid, update: true}, function(modalData) {
                   console.log(modalData);
                   self.execute_operation('edit_link', modalData)
                   .done(function(responseData, textStatus, jqXHR) {
                   })
                   .fail(function() {
                       console.log( "An error occured" );
                   });
               });

            });
        } else {
        }
    }

    add_link(linkData) {
        // check only one link per process
        try {
            var destProcType = innerRepresentation.processObj[linkData.to].type;
            var srcProcType = innerRepresentation.processObj[linkData.from].type;
        } catch(err) {
            /* buffer my have been selected */
            notify('Error:', 'Only <strong>Processes</strong> are allowed to have buffer', 'danger');
            return;
        }
        var srcConnectedEdges = network.getConnectedEdges(linkData.from)
        var srcEgressCount = srcConnectedEdges.reduce(function(acc, edgeID) {
            var edge = innerRepresentation.edges.get(edgeID);
            return edge.from == linkData.from ? acc+1 : 0; // sum outgoing edges
        }, 0);
        var dstConnectedEdges = network.getConnectedEdges(linkData.to)
        var dstIngressCount = dstConnectedEdges.reduce(function(acc, edgeID) {
            var edge = innerRepresentation.edges.get(edgeID);
            return edge.to == linkData.to ? acc+1 : 0; // sum outgoing edges
        }, 0);

        // validate link creation
        if (dstIngressCount == 1 && destProcType != 'multiplexer_in') {
            notify('Error:', 'Only <strong>multiplexer_in</strong> are allowed to have multiple ingress connections', 'danger');
            return;
        }
        if (srcEgressCount == 1 && srcProcType != 'multiplexer_out') {
            if (srcProcType != 'switch') { // switch can have multiple output
                notify('Error:', 'Only <strong>multiplexer_out</strong> are allowed to have multiple egress connections', 'danger');
                return;
            }
        }

        var self = this;
        var linkDataCorrectKeyname = {};
        linkDataCorrectKeyname.fromUUID = linkData.from;
        linkDataCorrectKeyname.toUUID = linkData.to;
        var pos = getCenterCoord(linkData.from, linkData.to)
        linkDataCorrectKeyname.x = pos.x;
        linkDataCorrectKeyname.y = pos.y;

        self.handleModal('AddLink', linkDataCorrectKeyname, function(modalData) {
            self.execute_operation('add_link', modalData)
            .done(function(responseData, textStatus, jqXHR) {
            })
            .fail(function() {
                console.log( "An error occured" );
            });
        });
    }

    handleDrop(dropData) {
        var self = this;
        if (dropData.type == 'process') {
            self.handleModal('AddProcess', dropData, function(modalData) {
                self.execute_operation('create_process', modalData)
                .done(function(responseData, textStatus, jqXHR) {
                })
                .fail(function() {
                    console.log( "An error occured" );
                });
            });

        } else if (dropData.type == 'multiplexer_input') {
            self.handleModal('AddMultInput', dropData, function(modalData) {
                console.log(modalData);
                self.execute_operation('create_mult_input', modalData)
                .done(function(responseData, textStatus, jqXHR) {
                })
                .fail(function() {
                    console.log( "An error occured" );
                });
            });
        } else if (dropData.type == 'multiplexer_output') {
            self.handleModal('AddMultOutput', dropData, function(modalData) {
                console.log(modalData);
                self.execute_operation('create_mult_output', modalData)
                .done(function(responseData, textStatus, jqXHR) {
                })
                .fail(function() {
                    console.log( "An error occured" );
                });
            });

        } else if (dropData.type == 'remote_input') {
            self.handleModal('AddRemoteInput', dropData, function(modalData) {
                self.execute_operation('create_process', modalData)
                .done(function(responseData, textStatus, jqXHR) {
                })
                .fail(function() {
                    console.log( "An error occured" );
                });
            });
        } else if (dropData.type == 'remote_output') {
        } else if (dropData.type == 'switch') {
            self.handleModal('AddSwitch', dropData, function(modalData) {
                console.log(modalData);
                self.execute_operation('create_switch', modalData)
                .done(function(responseData, textStatus, jqXHR) {
                })
                .fail(function() {
                    console.log( "An error occured" );
                });
            });
        } else {
            console.log(dropData);
        }
    }

    query_config_and_fill_form(uuid, modalType, uuidData, form_callback) {
        // var url_to_query = modalType == 'AddSwitch' ? url_get_connected_nodes : url_get_node_configuration;
        var url_to_query = url_get_node_configuration;
        var formID = 'form'+modalType;
        var formIDCustom = 'form'+modalType+'Custom';
        var data_connection = null;
        if (modalType == 'AddSwitch') {
            // get connected nodes names
            var connectedNodesName = []
            network.getConnectedEdges(uuid).reduce(function(acc, edgeID) {
                var edge = innerRepresentation.edges.get(edgeID);
                var node = innerRepresentation.nodes.get(edge.to);
                return edge.from == uuid ? connectedNodesName.push({name: node.name, uuid: node.id}) : 0; // sum outgoing edges
            }, 0);
            // create corresponding JSON
            data_connection = create_json_for_switch(connectedNodesName);
        }
        return $.ajax({
            type: "POST",
            url: url_to_query,
            data: JSON.stringify(uuidData),
            contentType: 'application/json; charset=utf-8',
        }).done(function( data ) {
                if (data_connection != null){
                    data.connections = data_connection;
                }
                fillForm(formID, formIDCustom, true, data);
                form_callback();
            }
        );
    }

    handleModal(modalType, dropData, callback) {
        var formID = 'form'+modalType;
        var formIDCustom = 'form'+modalType+'Custom';
        var modalID = 'modal'+modalType;

        $('#'+modalID).modal('show');
        $('#'+modalID+' li:first-child a[data-toggle="tab"]').tab('show') // Select first tab
        $('#processTypeDatableDiv').slideUp();
        $('#'+formIDCustom).empty();
        var pSelector = $('#'+modalID).find('[name="type"]');
        add_html_based_on_json(pSelector.val(), $('#'+formIDCustom));
        // Create custom_config html element on click
        $('#processTypeSelector').on('change', function() {
            $('#'+formIDCustom).empty();
            add_html_based_on_json($( this ).val(), $('#'+formIDCustom));
        })

        this.handleModalConfirm(modalType, dropData, callback);
    }

    handleModalConfirm(modalType, dropData, callback) {
        var formID = 'form'+modalType;
        var formIDCustom = 'form'+modalType+'Custom';
        var modalID = 'modal'+modalType;
        var confirmBtn = $('#'+modalID).find('button[confirm="1"]');
        // set correct button text
        if (dropData.update) {
            confirmBtn.text('Update');
            if (dropData.type == 'process') {
                $('#'+modalID).find('.modal-title').text('Update: '+innerRepresentation.processObj[dropData.puuid].name);
            } else {
                $('#'+modalID).find('.modal-title').text('Update: '+innerRepresentation.bufferObj[dropData.buuid].name);
            }
            // disable type change
            $('#processTypeSelector').prop('disabled', true);
            $('#showDataTableProcessType').hide();
        } else {
            confirmBtn.text('Create');
            $('#'+modalID).find('.modal-title').text('Create');
            $('#processTypeSelector').prop('disabled', false);
            $('#showDataTableProcessType').show();
        }

        // main logic
        confirmBtn.one('click', function(event) {
            if (validateForm(formID)) {
                var formData = getFormData(formID);
                $('#'+formID)[0].reset();
                var modalData = mergeInto(dropData, formData);
                var formDataCustom = getFormData(formIDCustom);
                $('#'+formIDCustom).empty();
                var modalData = mergeInto(modalData, {custom_config: formDataCustom });
                $('#'+modalID).modal('hide');
                callback(modalData);
            }
        });
    }

    handleNodesDrag(nodes) {
        var position = network.getPositions(nodes);
        for (var nodeUUID of nodes) {
            var data = {
                uuid: nodeUUID,
                nodeType: innerRepresentation.nodeType(nodeUUID),
                x: position[nodeUUID].x,
                y: position[nodeUUID].y
            }
            this.execute_operation('node_drag', data, true)
        }
    }

    execute_operation(operation, data, quick) {
        quick = quick === undefined ? false : quick;
        data.operation = operation;
        return $.ajax({
            type: "POST",
            url: url_flow_operation,
            data: JSON.stringify(data),
            contentType: 'application/json; charset=utf-8',
            beforeSend: function() { toggle_loading(true, quick); },
            complete: function() {
                toggle_loading(false, quick);
                if (!quick) {
                    innerRepresentation.resync_representation();
                }
            }
        });
    }

    simple_execute_operation(operation, data, oncomplete) {
        data.operation = operation;
        $.ajax({
            type: "POST",
            url: url_flow_operation,
            data: JSON.stringify(data),
            contentType: 'application/json; charset=utf-8',
            complete: function() {
                if (oncomplete !== undefined) {
                    oncomplete();
                }
            }
        });
    }

    startAll() {
        var data = {};
        data.operation = 'start_all';
        $.ajax({
            type: "POST",
            url: url_flow_operation,
            data: JSON.stringify(data),
            contentType: 'application/json; charset=utf-8'
        }).done(function() {
            alertManager.messageGroup['Process_manager_ready'].nobj.close();
        });
    }
}
