class FlowControl {
    constructor() {
        this._modalSuccess = false; // shows modal result (if user clicked cancel or not)
    }


    modalStateSucess() { this._modalSuccess = true; }
    modalStateReset() { this._modalSuccess = false; }

    add_link(data) {
        this.execute_operation('add_link', data)
        .done(function(responseData, textStatus, jqXHR) {
            // set correct fields depending on the server's response
            var edgeData = mergeInto(data, responseData);
            console.log(edgeData);
            innerRepresentation.addBuffer(edgeData);
        })
        .fail(function() {
            console.log( "An error occured" );
        });
    }

    handleDrop(dropData) {
        var self = this;
        if (dropData.type == 'process') {
            self.handleModal('AddProcess', dropData, function(modalData) {
                self.execute_operation('create_process', modalData)
                .done(function(responseData, textStatus, jqXHR) {
                    var nodeData = responseData;
                    console.log(nodeData);
                    innerRepresentation.addNode(nodeData);
                })
                .fail(function() {
                    console.log( "An error occured" );
                });
            });

        } else {
            console.log(dropData);
        }
    }

    handleModal(modalType, dropData, callback) {
        var self = this;
        var formID = 'form'+modalType;
        var modalID = 'modal'+modalType;
        $('#'+modalID).modal('show');
        $('#'+modalID).find('button[confirm="1"]').one('click', function(event) {
            if (validateForm(formID)) {
                var formData = getFormData(formID);
                $('#'+formID)[0].reset();
                var modalData = mergeInto(dropData, formData);
                $('#'+modalID).modal('hide');
                callback(modalData);
            }
        });
    }

    handleNodesDrag(nodes) {
        var position = network.getPositions(nodes);
        for (var nodeUUID of nodes) {
            var data = { puuid: nodeUUID, x: position[nodeUUID].x, y: position[nodeUUID].y }
            this.execute_operation('node_drag', data, true)
        }
    }

    execute_operation(operation, data, quick) {
        console.log(data);
        quick = quick === undefined ? false : quick;
        data.operation = operation;
        return $.ajax({
            type: "POST",
            url: url_flow_operation,
            data: JSON.stringify(data),
            contentType: 'application/json; charset=utf-8',
            beforeSend: function() { toggle_loading(true, quick); },
            complete: function() { toggle_loading(false, quick); }
        });
    }
}
