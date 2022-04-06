import iblrig.params as params
import datetime


pars = params.load_params_file()
print(f"\nPrevious value on [{pars['SCREEN_LUX_DATE']}] was [{pars['SCREEN_LUX_VALUE']}]")
value = input("\nPlease input the value of the luxometer (lux): ")
pars["SCREEN_LUX_VALUE"] = float(value)
pars["SCREEN_LUX_DATE"] = str(datetime.datetime.now().date())
print("  Updating local params file...")
lpars = params.update_params_file(pars)

print(
    "\nLux measurement updated on",
    f"[{lpars['SCREEN_LUX_DATE']}] with value [{lpars['SCREEN_LUX_VALUE']}]",
    "\n",
)
