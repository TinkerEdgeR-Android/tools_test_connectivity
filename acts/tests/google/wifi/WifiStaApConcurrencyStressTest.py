#!/usr/bin/env python3
#
#   Copyright 2018 - The Android Open Source Project
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.

import time
import pprint

from acts import asserts
from acts import signals
from acts import utils
from acts.test_decorators import test_tracker_info
from acts.test_utils.tel.tel_test_utils import WIFI_CONFIG_APBAND_2G
from acts.test_utils.tel.tel_test_utils import WIFI_CONFIG_APBAND_5G
from WifiStaApConcurrencyTest import WifiStaApConcurrencyTest
import acts.test_utils.wifi.wifi_test_utils as wutils

WifiEnums = wutils.WifiEnums

# Channels to configure the AP for various test scenarios.
WIFI_NETWORK_AP_CHANNEL_2G = 1
WIFI_NETWORK_AP_CHANNEL_5G = 36
WIFI_NETWORK_AP_CHANNEL_5G_DFS = 132

class WifiStaApConcurrencyStressTest(WifiStaApConcurrencyTest):
    """Stress tests for STA + AP concurrency scenarios.

    Test Bed Requirement:
    * At least two Android devices (For AP)
    * One Wi-Fi network visible to the device (for STA).
    """

    def __init__(self, controllers):
        WifiStaApConcurrencyTest.__init__(self, controllers)
        self.tests = ("test_stress_wifi_connection_2G_softap_2G",
                      "test_stress_wifi_connection_5G_softap_5G",
                      "test_stress_wifi_connection_5G_DFS_softap_5G",
                      "test_stress_wifi_connection_5G_softap_2G",
                      "test_stress_wifi_connection_5G_DFS_softap_2G",
                      "test_stress_wifi_connection_2G_softap_5G",
                      "test_stress_wifi_connection_5G_softap_2G_with_location_scan_on",
                      "test_stress_softap_2G_wifi_connection_2G",
                      "test_stress_softap_5G_wifi_connection_5G",
                      "test_stress_softap_5G_wifi_connection_5G_DFS",
                      "test_stress_softap_5G_wifi_connection_2G",
                      "test_stress_softap_2G_wifi_connection_5G",
                      "test_stress_softap_2G_wifi_connection_5G_DFS",
                      "test_stress_softap_5G_wifi_connection_2G_with_location_scan_on")

    def setup_class(self):
        self.dut = self.android_devices[0]
        self.dut_client = self.android_devices[1]
        wutils.wifi_test_device_init(self.dut)
        wutils.wifi_test_device_init(self.dut_client)
        # Do a simple version of init - mainly just sync the time and enable
        # verbose logging.  This test will fail if the DUT has a sim and cell
        # data is disabled.  We would also like to test with phones in less
        # constrained states (or add variations where we specifically
        # constrain).
        utils.require_sl4a((self.dut, self.dut_client))
        utils.sync_device_time(self.dut)
        utils.sync_device_time(self.dut_client)
        # Set country code explicitly to "US".
        self.dut.droid.wifiSetCountryCode(wutils.WifiEnums.CountryCode.US)
        self.dut_client.droid.wifiSetCountryCode(wutils.WifiEnums.CountryCode.US)
        # Enable verbose logging on the duts
        self.dut.droid.wifiEnableVerboseLogging(1)
        asserts.assert_equal(self.dut.droid.wifiGetVerboseLoggingLevel(), 1,
            "Failed to enable WiFi verbose logging on the softap dut.")
        self.dut_client.droid.wifiEnableVerboseLogging(1)
        asserts.assert_equal(self.dut_client.droid.wifiGetVerboseLoggingLevel(), 1,
            "Failed to enable WiFi verbose logging on the client dut.")

        req_params = ["AccessPoint", "dbs_supported_models", "stress_count"]
        opt_param = ["iperf_server_address"]
        self.unpack_userparams(
            req_param_names=req_params, opt_param_names=opt_param)

        if self.dut.model not in self.dbs_supported_models:
            asserts.skip(
                ("Device %s does not support dual interfaces.")
                % self.dut.model)

        if "iperf_server_address" in self.user_params:
            self.iperf_server = self.iperf_servers[0]
        if hasattr(self, 'iperf_server'):
            self.iperf_server.start()

        # Set the client wifi state to on before the test begins.
        wutils.wifi_toggle_state(self.dut_client, True)

        # Init extra devices
        if len(self.android_devices) > 2:
            wutils.wifi_test_device_init(self.android_devices[2])
            utils.sync_device_time(self.android_devices[2])
            self.android_devices[2].droid.wifiSetCountryCode(wutils.WifiEnums.CountryCode.US)
            self.android_devices[2].droid.wifiEnableVerboseLogging(1)
            asserts.assert_equal(self.android_devices[2].droid.wifiGetVerboseLoggingLevel(), 1,
                "Failed to enable WiFi verbose logging on the client dut.")

    """Helper Functions"""

    def verify_traffic_between_softap_clients(self):
        ad1 = self.dut_client
        ad2 = self.android_devices[2]
        ad1_ip = ad1.droid.connectivityGetIPv4Addresses('wlan0')[0]
        ad2_ip = ad2.droid.connectivityGetIPv4Addresses('wlan0')[0]
        # Ping each other
        asserts.assert_true(
            utils.adb_shell_ping(ad1, count=10, dest_ip=ad2_ip, timeout=20),
            "%s ping %s failed" % (ad1.serial, ad2_ip))
        asserts.assert_true(
            utils.adb_shell_ping(ad2, count=10, dest_ip=ad1_ip, timeout=20),
            "%s ping %s failed" % (ad2.serial, ad1_ip))

    def verify_traffic_between_onhub_clients(self, interface):
            ad1 = self.dut
            ad2 = self.android_devices[2]
            ad1_ip = ad1.droid.connectivityGetIPv4Addresses(interface)[0]
            ad2_ip = ad2.droid.connectivityGetIPv4Addresses('wlan0')[0]
            # Ping each other
            asserts.assert_true(
                utils.adb_shell_ping(ad1, count=10, dest_ip=ad2_ip, timeout=20),
                "%s ping %s failed" % (ad1.serial, ad2_ip))
            asserts.assert_true(
                utils.adb_shell_ping(ad2, count=10, dest_ip=ad1_ip, timeout=20),
                "%s ping %s failed" % (ad2.serial, ad1_ip))

    def verify_wifi_full_on_off(self, network, softap_config, interface):
        wutils.wifi_toggle_state(self.dut, True)
        self.connect_to_wifi_network_and_verify((network, self.dut))
        self.run_iperf_client((network, self.dut))
        self.run_iperf_client((softap_config, self.dut_client))
        if len(self.android_devices) > 2:
            self.log.info("Testbed has extra android devices, do more validation")
            self.verify_traffic_between_onhub_clients(interface)
        wutils.wifi_toggle_state(self.dut, False)

    def verify_softap_full_on_off(self, network, softap_band):
        softap_config = self.start_softap_and_verify(softap_band)
        self.run_iperf_client((network, self.dut))
        self.run_iperf_client((softap_config, self.dut_client))
        if len(self.android_devices) > 2:
            self.log.info("Testbed has extra android devices, do more validation")
            self.verify_traffic_between_softap_clients()
        wutils.stop_wifi_tethering(self.dut)

    """Tests"""
    @test_tracker_info(uuid="615997cc-8290-4af3-b3ac-1f5bd5af6ed1")
    def test_stress_wifi_connection_2G_softap_2G(self):
        """Tests connection to 2G network the enable/disable SoftAp on 2G N times.
        """
        self.configure_ap(channel_2g=WIFI_NETWORK_AP_CHANNEL_2G)
        wutils.wifi_toggle_state(self.dut, True)
        self.connect_to_wifi_network_and_verify((self.wpapsk_2g, self.dut))
        for count in range(self.stress_count):
            self.log.info("Iteration %d", count+1)
            self.verify_softap_full_on_off(self.wpapsk_2g, WIFI_CONFIG_APBAND_2G)
        raise signals.TestPass(details="", extras={"Iterations":"%d" %
            self.stress_count, "Pass":"%d" %(count+1)})

    @test_tracker_info(uuid="03362d54-a624-4fb8-ad97-7abb9e6f655c")
    def test_stress_wifi_connection_5G_softap_5G(self):
        """Tests connection to 5G network followed by bringing up SoftAp on 5G.
        """
        self.configure_ap(channel_5g=WIFI_NETWORK_AP_CHANNEL_5G)
        wutils.wifi_toggle_state(self.dut, True)
        self.connect_to_wifi_network_and_verify((self.wpapsk_5g, self.dut))
        for count in range(self.stress_count):
            self.log.info("Iteration %d", count+1)
            self.verify_softap_full_on_off(self.wpapsk_5g, WIFI_CONFIG_APBAND_5G)
        raise signals.TestPass(details="", extras={"Iterations":"%d" %
            self.stress_count, "Pass":"%d" %(count+1)})

    @test_tracker_info(uuid="fdda4ff2-38d5-4398-9a59-c7cee407a2b3")
    def test_stress_wifi_connection_5G_DFS_softap_5G(self):
        """Tests connection to 5G DFS network followed by bringing up SoftAp on 5G.
        """
        self.configure_ap(channel_5g=WIFI_NETWORK_AP_CHANNEL_5G_DFS)
        wutils.wifi_toggle_state(self.dut, True)
        self.connect_to_wifi_network_and_verify((self.wpapsk_5g, self.dut))
        for count in range(self.stress_count):
            self.log.info("Iteration %d", count+1)
            self.verify_softap_full_on_off(self.wpapsk_5g, WIFI_CONFIG_APBAND_5G)
        raise signals.TestPass(details="", extras={"Iterations":"%d" %
            self.stress_count, "Pass":"%d" %(count+1)})

    @test_tracker_info(uuid="b3621721-7714-43eb-8438-b578164b9194")
    def test_stress_wifi_connection_5G_softap_2G(self):
        """Tests connection to 5G network followed by bringing up SoftAp on 2G.
        """
        self.configure_ap(channel_5g=WIFI_NETWORK_AP_CHANNEL_5G)
        wutils.wifi_toggle_state(self.dut, True)
        self.connect_to_wifi_network_and_verify((self.wpapsk_5g, self.dut))
        for count in range(self.stress_count):
            self.log.info("Iteration %d", count+1)
            self.verify_softap_full_on_off(self.wpapsk_5g, WIFI_CONFIG_APBAND_2G)
        raise signals.TestPass(details="", extras={"Iterations":"%d" %
            self.stress_count, "Pass":"%d" %(count+1)})

    @test_tracker_info(uuid="bde1443f-f912-408e-b01a-537548dd023c")
    def test_stress_wifi_connection_5G_DFS_softap_2G(self):
        """Tests connection to 5G DFS network followed by bringing up SoftAp on 2G.
        """
        self.configure_ap(channel_5g=WIFI_NETWORK_AP_CHANNEL_5G_DFS)
        wutils.wifi_toggle_state(self.dut, True)
        self.connect_to_wifi_network_and_verify((self.wpapsk_5g, self.dut))
        for count in range(self.stress_count):
            self.verify_softap_full_on_off(self.wpapsk_5g, WIFI_CONFIG_APBAND_2G)
        raise signals.TestPass(details="", extras={"Iterations":"%d" %
            self.stress_count, "Pass":"%d" %(count+1)})

    @test_tracker_info(uuid="2b6a891a-e0d6-4660-abf6-579099ce6924")
    def test_stress_wifi_connection_2G_softap_5G(self):
        """Tests connection to 2G network followed by bringing up SoftAp on 5G.
        """
        self.configure_ap(channel_2g=WIFI_NETWORK_AP_CHANNEL_2G)
        wutils.wifi_toggle_state(self.dut, True)
        self.connect_to_wifi_network_and_verify((self.wpapsk_2g, self.dut))
        for count in range(self.stress_count):
            self.log.info("Iteration %d", count+1)
            self.verify_softap_full_on_off(self.wpapsk_2g, WIFI_CONFIG_APBAND_2G)
        raise signals.TestPass(details="", extras={"Iterations":"%d" %
            self.stress_count, "Pass":"%d" %(count+1)})

    @test_tracker_info(uuid="f28abf22-9df0-4500-b342-6682ca305e60")
    def test_stress_wifi_connection_5G_softap_2G_with_location_scan_on(self):
        """Tests connection to 5G network followed by bringing up SoftAp on 2G
        with location scans turned on.
        """
        self.configure_ap(channel_5g=WIFI_NETWORK_AP_CHANNEL_5G)
        self.turn_location_on_and_scan_toggle_on()
        wutils.wifi_toggle_state(self.dut, True)
        self.connect_to_wifi_network_and_verify((self.wpapsk_5g, self.dut))
        for count in range(self.stress_count):
            self.log.info("Iteration %d", count+1)
            self.verify_softap_full_on_off(self.wpapsk_5g, WIFI_CONFIG_APBAND_2G)
        raise signals.TestPass(details="", extras={"Iterations":"%d" %
            self.stress_count, "Pass":"%d" %(count+1)})

    @test_tracker_info(uuid="0edb1500-6c60-442e-9268-a2ad9ee2b55c")
    def test_stress_softap_2G_wifi_connection_2G(self):
        """Tests enable SoftAp on 2G then connection/disconnection to 2G network for N times.
        """
        self.configure_ap(channel_2g=WIFI_NETWORK_AP_CHANNEL_2G)
        softap_config = self.start_softap_and_verify(
                WIFI_CONFIG_APBAND_2G, check_connectivity=False)
        for count in range(self.stress_count):
            self.log.info("Iteration %d", count+1)
            self.verify_wifi_full_on_off(self.wpapsk_2g, softap_config, 'wlan1')
        raise signals.TestPass(details="", extras={"Iterations":"%d" %
            self.stress_count, "Pass":"%d" %(count+1)})

    @test_tracker_info(uuid="162a6679-edd5-4daa-9f25-75d79cf4bb4a")
    def test_stress_softap_5G_wifi_connection_5G(self):
        """Tests enable SoftAp on 5G then connection/disconnection to 5G network for N times.
        """
        self.configure_ap(channel_5g=WIFI_NETWORK_AP_CHANNEL_5G)
        softap_config = self.start_softap_and_verify(
                WIFI_CONFIG_APBAND_5G, check_connectivity=False)
        for count in range(self.stress_count):
            self.log.info("Iteration %d", count+1)
            self.verify_wifi_full_on_off(self.wpapsk_5g, softap_config, 'wlan1')
        raise signals.TestPass(details="", extras={"Iterations":"%d" %
            self.stress_count, "Pass":"%d" %(count+1)})

    @test_tracker_info(uuid="ee98f2dd-c4f9-4f48-ab59-f577267760d5")
    def test_stress_softap_5G_wifi_connection_5G_DFS(self):
        """Tests enable SoftAp on 5G then connection/disconnection to 5G DFS network for N times.
        """
        self.configure_ap(channel_5g=WIFI_NETWORK_AP_CHANNEL_5G_DFS)
        softap_config = self.start_softap_and_verify(
                WIFI_CONFIG_APBAND_5G, check_connectivity=False)
        for count in range(self.stress_count):
            self.log.info("Iteration %d", count+1)
            self.verify_wifi_full_on_off(self.wpapsk_5g, softap_config, 'wlan1')
        raise signals.TestPass(details="", extras={"Iterations":"%d" %
            self.stress_count, "Pass":"%d" %(count+1)})

    @test_tracker_info(uuid="b50750b5-d5b9-4687-b9e7-9fb15f54b428")
    def test_stress_softap_5G_wifi_connection_2G(self):
        """Tests enable SoftAp on 5G then connection/disconnection to 2G network for N times.
        """
        self.configure_ap(channel_2g=WIFI_NETWORK_AP_CHANNEL_2G)
        softap_config = self.start_softap_and_verify(
                WIFI_CONFIG_APBAND_5G, check_connectivity=False)
        for count in range(self.stress_count):
            self.log.info("Iteration %d", count+1)
            self.verify_wifi_full_on_off(self.wpapsk_2g, softap_config, 'wlan1')
        raise signals.TestPass(details="", extras={"Iterations":"%d" %
            self.stress_count, "Pass":"%d" %(count+1)})

    @test_tracker_info(uuid="9a2865db-8e4b-4339-9999-000ce9b6970b")
    def test_stress_softap_2G_wifi_connection_5G(self):
        """Tests enable SoftAp on 2G then connection/disconnection to 5G network for N times.
        """
        self.configure_ap(channel_5g=WIFI_NETWORK_AP_CHANNEL_5G)
        softap_config = self.start_softap_and_verify(
                WIFI_CONFIG_APBAND_2G, check_connectivity=False)
        for count in range(self.stress_count):
            self.log.info("Iteration %d", count+1)
            self.verify_wifi_full_on_off(self.wpapsk_5g, softap_config, 'wlan1')
        raise signals.TestPass(details="", extras={"Iterations":"%d" %
            self.stress_count, "Pass":"%d" %(count+1)})

    @test_tracker_info(uuid="add6609d-91d6-4b89-94c5-0ad8b941e3d1")
    def test_stress_softap_2G_wifi_connection_5G_DFS(self):
        """Tests enable SoftAp on 2G then connection/disconnection to 5G DFS network for N times.
        """
        self.configure_ap(channel_5g=WIFI_NETWORK_AP_CHANNEL_5G_DFS)
        softap_config = self.start_softap_and_verify(
                WIFI_CONFIG_APBAND_2G, check_connectivity=False)
        for count in range(self.stress_count):
            self.log.info("Iteration %d", count+1)
            self.verify_wifi_full_on_off(self.wpapsk_5g, softap_config, 'wlan1')
        raise signals.TestPass(details="", extras={"Iterations":"%d" %
            self.stress_count, "Pass":"%d" %(count+1)})

    @test_tracker_info(uuid="ee42afb6-99d0-4330-933f-d4dd8c3626c6")
    def test_stress_softap_5G_wifi_connection_2G_with_location_scan_on(self):
        """Tests enable SoftAp on 5G then connection/disconnection to 2G network for N times
        with location scans turned on.
        """
        self.configure_ap(channel_2g=WIFI_NETWORK_AP_CHANNEL_2G)
        self.turn_location_on_and_scan_toggle_on()
        softap_config = self.start_softap_and_verify(
                WIFI_CONFIG_APBAND_5G, check_connectivity=False)
        for count in range(self.stress_count):
            self.log.info("Iteration %d", count+1)
            self.verify_wifi_full_on_off(self.wpapsk_2g, softap_config, 'wlan0')
        raise signals.TestPass(details="", extras={"Iterations":"%d" %
            self.stress_count, "Pass":"%d" %(count+1)})
