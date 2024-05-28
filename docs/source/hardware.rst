Hardware Guide
==============


Upgrading Xonar AE to Bpod HiFi Module
------------------------------------------------

Background
""""""""""

In their original design, IBL’s behavioral training rigs relied on a consumer-grade sound-card - the `ASUS Xonar AE <https://www.asus.com/motherboards-components/sound-cards/gaming/xonar-ae/>`_ - for delivering auditory cues to the subject. We have identified the Xonar AE as a weak point in the design of the training rig as this choice of hardware has several severe drawbacks:

*  Synchronization between individual components of the rig relies on TTL Signals, a standardized way of communicating between digital devices.
   With the Xonar sound-card, we emulate TTL pulses on one of the soundcard’s analog audio outputs.
   The resulting signal does not conform well to the TTL standard since (a) we cannot guarantee the required signal rise-times, and (b) pulse-amplitude depends on the computer’s audio volume and impedance settings. The effects are increased latencies and accidental misconfigurations.
   The latter have the potential to cause synchronization issues and more problems further down the pipeline.
*  The ASUS Xonar AE does not seem to be a particularly robust piece of equipment - we’ve experienced several catastrophic failures across our rigs at IBL. Replacement hardware is increasingly hard to come by as the Asus Xonar AE is not being produced anymore.
*  The soundcard’s driver has been causing issues with specific Windows updates that require manual intervention / rollback of the respective updates.
*  There is no Windows 11 specific driver available.

For these reasons, we decided to replace the Xonar AE with the `Bpod HiFi Module HD <https://sanworks.io/shop/viewproduct?productID=1033>`_ by Sanworks:
The HiFi Module is capable of delivering high fidelity sound stimuli at low latencies, supports proper TTL signaling as well as serial communication with the Bpod Finite State Machine and does not require any dedicated drivers.
The upgrade procedure is straightforward and should take no longer than 5-10 minutes.

Requirements
""""""""""""

To replace your existing Xonar AE with the Bpod HiFi Module HD you will require the following:

*  1x Bpod HiFi Module HD
*  1x Micro-USB to USB-A cable
*  1x Ethernet cable (RJ45)
*  1x RCA to 3.5 mm audio adapter
*  1x 3 mm flathead screwdriver

.. warning:: Support for the Bpod HiFi Module was introduced with IBLRIG 8.16.0 and will not be backported to older version of IBLRIG.
             Make sure to upgrade to the latest version of IBLRIG before continuing with this guide.

Upgrade Procedure
"""""""""""""""""

1. Use the 3 mm flathead screwdriver to unscrew the BNC to wire adapter from the amplifier board.
   While the adapter itself is not needed anymore we will continue using the BNC cable.
   Leave the other end of the BNC cable plugged into the Bpod as it is.

   .. figure:: img/amp2x15_labels.png
      :width: 100%
      :class: with-border

      Disconnect the BNC to wire adapter from the amplifier board.

2. Unplug the 3.5 mm audio cable from the Xonar AE sound card on the backside of the rig's computer.
   Leave the other end of the 3.5 mm audio cable connected to the amplifier board.

   .. figure:: img/xonar_labels.png
      :width: 100%
      :class: with-border

      Unplug the 3.5 mm audio cable from the Xonar AE sound card.

3. Connect the Bpod HiFi Module as follows:

   * the BNC cable connects to TTL In 2 of the Bpod (cf. step 1),
   * the 3.5 mm audio cable connects to the amplifier board via the RCA adapter (cf. step 2),
   * the USB cable connects to the rig's computer
   * the Ethernet cable connects to one of the Bpod's Module ports.
     Warning: Bpod uses identical connectors for its Behavior ports - do not mix them up!

   .. figure:: img/hifi_labels.png
      :width: 100%
      :class: with-border

      The Bpod HiFi Modules and its connections.

4. Open `C:/iblrigv8/settings/hardware_settings.yaml` in a text-editor.
   Find the section `device_sound` and adapt it as follows:

   .. code-block:: yaml

      device_sound:
        OUTPUT: hifi
        COM_SOUND: COMx  # replace with the HiFi Module's actual COM port!
        AMP_TYPE: AMP2X15

   .. tip::

      Use Windows' device manager to identify the HiFi Module's COM port.
      The device should show up in the section labelled "Ports (COM & LPT)" after plugging it in.

5. Start IBLRIG and make sure that the hardware validation during start-up does not find any issues.
   Finally, start a session and verify that you can hear the audio cues.