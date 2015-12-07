# python3.4
# Copyright (C) 2014 The Android Open Source Project
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may not
# use this file except in compliance with the License. You may obtain a copy of
# the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations under
# the License.

from acts.logger import LoggerProxy

log = LoggerProxy()

def setup_native_bluetooth(native_devices):
  for n in native_devices:
    droid = n.droid
    droid.BluetoothBinderInitInterface()
    droid.BluetoothBinderEnable()
    droid.BluetoothBinderRegisterBLE()
