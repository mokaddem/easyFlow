class AlertsManager {
    constructor() {
        this.alertsSource = new EventSource(url_alert_stream);
        this.setup_listener();
        this.messageGroup = {};
    }

    close_listener() {
        this.alertsSource.close();
    }

    setup_listener() {
        var self = this;
        this.alertsSource.onmessage = function(e) {
            self.handle_message(e.data);
        };
        this.alertsSource.onopen = function (e) {};
        this.alertsSource.onerror = function (e) {};

    }

    handle_message(message) {
        // message is a JSON composed of [title, message, type, group, [totalCount]]
        // message can be either singleton or forming a group.
        // A group of message must have a length indicating the progress (represented by a progressbar)
        // The first message setup the group.
        var self = this;
        try {
            var jsonData = JSON.parse(message);
            if (jsonData.message == 1) { return; } // ignore control messages

            var group = jsonData.group;
            if (group == 'singleton' || group === undefined) {
                // directly emit the notification
                notify(jsonData.title+': ', jsonData.message, jsonData.type);
            } else {
                // register group
                // incrementally update the pb
                var completed = 0;
                if (this.messageGroup[group] === undefined) { // group does not exists
                    if (jsonData.totalCount > 0) { //no total count
                        notify(jsonData.title+': ', jsonData.message, jsonData.type)
                    } else {
                        var nobj = $.notify({
                                icon: 'glyphicon glyphicon-refresh',
                                title: '<strong>'+jsonData.title+': </strong>',
                                message: jsonData.message,
                                progress: completed
                            },{
                                type: jsonData.type,
                                showProgressbar: showPB,
                                delay: 0,
                                placement: {
                                    from: "top",
                                    align: "right"
                                },
                                z_index: 3000,
                                animate: {
                                    enter: 'animated bounceInDown',
                                    exit: 'animated flipOutX'
                                }
                        });
                        this.messageGroup[group] = {left: jsonData.totalCount, total: jsonData.totalCount, nobj: nobj}
                    }
                } else { // update the notification
                    var completed = Math.round(100*(this.messageGroup[group].total-this.messageGroup[group].left+1)/this.messageGroup[group].total);
                    this.messageGroup[group].nobj.update({
                        message: jsonData.message,
                        title: '<strong>'+jsonData.title+': </strong>',
                        progress: completed
                    });
                    this.messageGroup[group].left = this.messageGroup[group].left-1;
                    // group of messages completed -> remove data
                    if (this.messageGroup[group].left == 0) {
                        this.messageGroup[group].nobj.update({
                            message: '',
                            title: '<strong>'+'Operation completed'+' </strong>',
                            progress: completed,
                            type: 'success'
                        });
                        setTimeout(function() {
                            self.messageGroup[group].nobj.close();
                            delete self.messageGroup[group];
                        }, 5000);
                    }
                }
            }
        } catch(e) { /* JSONDecodeError */ console.log('error', message);}
    }

}
