# Creality Control Integration for Home Assistant

This custom integration allows Home Assistant users to monitor and control their Creality 3D printers. It offers capabilities such as viewing current print status and sending pause/resume and stop commands directly from the Home Assistant interface. This integration has been specifically tested with the Creality Halot resin printer and Creality K1SE FDM printer, and is based on WebSocket communication discovered through Wireshark capture while running the Halot software connected to the printer.

## Features

- **Print Status Monitoring**: Track the status of ongoing prints, including progress, remaining time, current layer, and more.
- **Print Control**: Directly pause/resume and stop prints from within Home Assistant.
- **Notifications**: Configure Home Assistant to notify you about print completions or issues (additional configuration required).

## Prerequisites

- A compatible Creality 3D printer connected to your network.
- Home Assistant Core 2021.6.0 or newer.

## Installation

### Option 1: HACS (Recommended)

1. Make sure you have [HACS](https://hacs.xyz/) installed.
2. Open HACS and go to **Integrations**.
3. Click the three dots menu and select **Custom repositories**.
4. Add this repository URL: `https://github.com/SiloCityLabs/Creality-Control`
5. Select **Integration** as the category.
6. Click **Add** and then **Install**.
7. Restart Home Assistant.
8. Navigate to **Configuration** > **Integrations** and click **+ Add Integration**.
9. Search for "Creality Control" and input your printer's details as prompted.

### Option 2: Manual Installation

1. Clone this repository or download the latest release.
2. Copy the `custom_components/creality_control` folder to your `custom_components` directory in your Home Assistant configuration directory.
3. Restart Home Assistant to recognize the new integration.
4. Navigate to **Configuration** > **Integrations** and click **+ Add Integration**.
5. Search for "Creality Control" and input your printer's details as prompted.

## Configuration

You will need the following information to set up the integration:

- **Host**: IP address of your Creality printer.
- **Port**: Network port for the printer (default: `9999` for K1SE and newer printers, `18188` for older Halot series).
- **Password**: Your printer's password, if set. For K1SE printers, you can often leave this field empty if no password has been configured.

## Important Considerations

- **Printer Online**: Ensure your printer is online and connected to the same network as Home Assistant for successful integration. The integration is specifically tested with the Creality Halot resin printer and Creality K1SE FDM printer.
- **Control Limitations**: Pause/Resume and Stop commands are only functional when there is an active print job. Home Assistant does not support uploading print files or starting prints due to limitations.

## Support

For support, questions, or contributions, please visit the [GitHub issue tracker](https://github.com/SiloCityLabs/Creality-Control/issues).

## Disclaimer

This integration is not officially affiliated with Creality. Use it at your own risk. Always ensure your printer's firmware is up to date with the latest version recommended by Creality. The integration's communication mechanism was discovered via Wireshark capture while running Halot software and connected to the printer, and it may not apply universally to all Creality printers.

## License

This Home Assistant integration is released under the [MIT License](LICENSE).

[!["Buy Me A Coffee"](https://www.buymeacoffee.com/assets/img/custom_images/orange_img.png)](https://paypal.me/ldrrp)
