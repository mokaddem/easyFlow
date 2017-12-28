class FlowControl {
    constructor() {
        this._modalSuccess = false; // shows modal result (if user clicked cancel or not)
        this.updateSocket = io.connect('http://' + document.domain + ':' + location.port + '/update');

        this.updateSocket.on('update', function(msg) {
            console.log('Received: ' + msg.data);
            var state = msg.state;
        });
    }

    update() {
        this.updateSocket.emit('updateRequest', {data: "Here's some text that the server is urgently awaiting!"});
        return false;
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
            if (validateForm(formID, modalID)) {
                var formData = getFormData(formID);
                $('#'+formID)[0].reset();
                var modalData = mergeInto(dropData, formData);
                $('#'+modalID).modal('hide');
                callback(modalData);
            }
        });
    }

    execute_operation(operation, data) {
        data.operation = operation;
        return $.ajax({
            type: "POST",
            url: url_flow_operation,
            data: JSON.stringify(data),
            contentType: 'application/json; charset=utf-8',
            beforeSend: function() { toggle_loading(true); },
            complete: function() { toggle_loading(false); }
        });
    }
}
