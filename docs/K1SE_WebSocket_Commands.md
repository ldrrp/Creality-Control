| name              | info                                       | json                                              |
| ----------------- | ------------------------------------------ | ------------------------------------------------- |
| restartFirmware   | Reboot printer.                            | `{"method":"set","params":{"restartFirmware":1}}` |
| repoPlrStatus:1   | Resume after unexpected stop.              | `{"method":"set","params":{"repoPlrStatus":1}}`   |
| repoPlrStatus:0   | Cancel after unexpected stop.              | `{"method":"set","params":{"repoPlrStatus":0}}`   |
| reqGcodeFile      | Request list of G-code files               | `{"method": "get", "params": {"reqGcodeFile": 1}}` |
| reqProbedMatrix   | Request probed bed leveling matrix         | `{"method": "get", "params": {"reqProbedMatrix": 1}}`                                 | 
| ReqPrinterPara    | Request printer parameters                 | `{"method": "get", "params": {"ReqPrinterPara": 1}}`                                  | 
| autohome:X        | Auto-home X axis                           | `{"method": "set", "params": {"autohome": "X"}}`                                      | 
| autohome:Y        | Auto-home Y axis                           | `{"method": "set", "params": {"autohome": "Y"}}`                                      | 
| autohome:X Y      | Auto-home both X and Y axes                | `{"method": "set", "params": {"autohome": "X Y"}}`                                    | 
| fanCase           | Set case fan speed                         | `{"method": "set", "params": {"fanCase": "<numeric_value>"}}`                         | 
| lightSw           | Toggle printer light                       | `{"method": "set", "params": {"lightSw": "<numeric_value>"}}`                         | 
| bedTempControl    | Set bed temperature by index               | `{"method": "set", "params": {"bedTempControl": {"num": "<index>", "val": "<temp>"}}}`| 
| opGcodeFile:delete| Delete print file                          | `{"method": "set", "params": {"opGcodeFile": "deleteprt:<t>/<e>"}}`                   | 
| opGcodeFile:print | Start print job                            | `{"method": "set", "params": {"opGcodeFile": "printprt:<t>/<e>"}}`                    | 
| setZOffset:+      | Increase Z offset                          | `{"method": "set", "params": {"setZOffset": "+<Z>"}}`                                 | 
| setZOffset:-      | Decrease Z offset                          | `{"method": "set", "params": {"setZOffset": "-<Z>"}}`                                 | 
| setPosition:Y     | Move Y axis to position                    | `{"method": "set", "params": {"setPosition": "Y<distance> F3000"}}`                   | 
| rmProbedMatrix    | Remove stored probe matrix                 | `{"method": "set", "params": {"rmProbedMatrix": 1}}`                                  | 
| stop:1            | Stop current operation                     | `{"method": "set", "params": {"stop": 1}}`                                            | 
| stop:0            | Resume operation                           | `{"method": "set", "params": {"stop": 0}}`                                            | 