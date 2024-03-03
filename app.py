import os
import base64
import requests
import json
import io
import streamlit as st
from PIL import Image, ExifTags
import math

# Environment Variables
openai_api_key = os.environ.get("OPENAI_API_KEY")
vehicle_data_api_key = os.environ.get("VEHICLE_DATA_API_KEY")

# Streamlit Configuration
st.set_page_config(
    page_title="Collision AI",
    page_icon=":Car:",
    layout="wide"
)

# Streamlit Page
def display_page():

    st.sidebar.header('Vehicle Damage Upload')

    # Image upload
    images = st.sidebar.file_uploader("Upload Damage Images", accept_multiple_files=True, type=['png', 'jpg', 'jpeg'])

    def correct_image_orientation(image):
        try:
            for orientation in ExifTags.TAGS.keys():
                if ExifTags.TAGS[orientation] == 'Orientation':
                    break
            exif = dict(image._getexif().items())

            if exif[orientation] == 3:
                image = image.rotate(180, expand=True)
            elif exif[orientation] == 6:
                image = image.rotate(270, expand=True)
            elif exif[orientation] == 8:
                image = image.rotate(90, expand=True)
        except (AttributeError, KeyError, IndexError):
            # Cases: image doesn't have getexif
            pass
        return image

    # Display uploaded images in the sidebar
    if images:
        for uploaded_file in images:
            image = Image.open(uploaded_file)
            corrected_image = correct_image_orientation(image)
            st.sidebar.image(corrected_image, caption='Uploaded Image', use_column_width=True)

    # Vehicle information input
    st.sidebar.header("Vehicle Information")
    vehicle_reg = st.sidebar.text_input("Vehicle Registration Number")
    FNOL_description = st.sidebar.text_area("First Notification of Loss Description")
    

    # Process images button
    if st.sidebar.button("Process Images"):
        if images and vehicle_reg and FNOL_description:

            # Replacement costs used to approximate repair costs, ideally we would use an API connection with parts suppliers
            replacement_costs = {
                'Side Mirror': 300,
                'Bonnet': 1000,
                'Door Glass': 200,
                'Door Handle': 200,
                'Exhaust': 500,
                'Front Bumper': 600,
                'Front Door': 800,
                'Headlamp': 400,
                'Lower Grille': 150,
                'Number Plate': 20,
                'PDC Sensor': 150,
                'Quarter Panel': 1500,
                'Rear Bumper': 500,
                'Rear Door': 800,
                'Rear Emblem': 50,
                'Rear Glass': 300,
                'Rear Inner Lamp': 150,
                'Rear Outer Lamp': 200,
                'Rear Reflector': 50,
                'Sill Panel': 600,
                'Tailgate': 800,
                'Tailgate Spoiler': 200,
                'Third Brake Light': 100,
                'Tow Eye Cap': 30,
                'Upper Grille': 200,
                'Wheel': 200,
                'Tyre': 150,
                'Windshield': 400,
                'Wing': 300,
                'Airbag': 2000,
                'radiator support': 1000,
                'condenser': 500,
                'radiatior': 500,
                'wheel alignment': 100,
                'road test': 100,
                'diagnostic trouble code': 100,
            }

            # Used for the one-shot prompt to GPT-4 for repair plan creation
            json_example = """
            Note: Before assessing damage from images, it's essential to distinguish between a vehicle's original body lines and damage-induced irregularities. Shadows and reflections can be deceptive and may not necessarily indicate damage. Knowing the vehicle's design is key to not mistaking design features for dents or creases. Always compare with the vehicle's standard lines to avoid misinterpretation caused by image lighting and angle effects. Normal gaps between panels must also be considered, as they may appear misaligned or damaged to the untrained eye.
            Note: Minor damage, repairable within an hour, is often indicated by light scratches or small dents where the panel's reflective quality remains uniform, and there are no alterations in panel gaps or paint texture. Damage requiring between 2-3 hours to repair can vary, but here are some things to look out for: Dents or creases where the shadows and usual contours of the panel are disrupted. "Spider-webbing" where the impact causes the paint to crack (more common on plastic parts like bumpers). Deeper scratches or scrapes where paint may be visibly missing. These damages might be repairable depending on the repair limits for the damaged panel. Repair work extending to 4-6 hours typically involves significant deformation of the panel with highly visible creases and distortion in reflections, along with paint that is visibly cracked or flaked. It is extremely important to observe the overall vehicle since what might appear to be distortion from damage may just be the body lines of the vehicle. Extensive damage that exceeds 6 hours is characterized by substantial panel gaps misalignment, severe creasing and deformation of the panel, and extensive areas of compromised paint, suggesting the need for complex structural repairs or complete panel replacement.
            Note: Be sure to examine the surrounding in the images, some objects may cause irregular reflections that can fool an unwary estimator.
            {
                // "reg_no" is the vehicle registration number. Leave it as an empty string if not available.
                "reg_no": "GJ14WKH",

                // "damage_description" describes the visible damage in the images and the repair plan.
                "damage_description": "The images show a VW Golf that has been damaged in the front. The hood has been pushed back into the vehicle and is severely damaged with massive creases and severe misalignment, well beyond reasonable repair limits. Due to this severe damage the hood hinges and lacth must be replaced. The right headlamp is damaged and has a cracked lens. The impact has shoved the right headlamp into the right fender, so repair and painting will be required. The front grille is missing and will require replacement. No damage is visible to the right or left fenders and wheels. The front bumper has been damaged and is not sitting correctly, it also has various deep scratches and cracks. The overall repair plan will be as follows: Replace front bumper, replace hood, replace right headlamp, replace the front grille, replace hood hinges, replace hood latch, and repair the right fender. The shop must also check the radiator support, condenser, radiator, LH headlamp, lower bumper grilles, and LH fender for damage.",

                // "parts_list" is an array where each object represents a car part needing attention. This means the part requires replacement, repair, or painting depending on the severity of the damage.
                // Each object can contain the following fields:
                // - "part": Name or type of the part (e.g. "Bumper", "Hood", "Headlamp", "Fender", "Fog Lamp Grille", "Tow Eye Cap", "Wheel", "Tyre", "Suspension Components", etc.)
                // - "position": Location on the vehicle, if applicable. ("LH", "RH", "FRONT", "REAR", "LF", "RF", "LR", or "RR" are the valid options.) This field must always be present, even if empty.
                // - "s_r": A boolean indicating whether the part should be stripped and refitted (true/false).
                // - "repair": A boolean indicating if the part should be repaired (true/false). (CANNOT BE USED WITH "replace") Only select true if damage is visible and without question. 
                // - "replace": A boolean indicating if the part should be replaced (true/false). (CANNOT BE USED WITH "repair") Only select true if damage is visible and without question. Non-painted parts like tyres, wheels, and headlamps must be replaced if clearly damaged.
                // - "paint": A boolean indicating if the part needs painting after repair or replacement (true/false).
                // Note: "repair" and "replace" are mutually exclusive. When determining whether to repair or replace a part, consider the cost of the part, the cost of labour, and the time required to repair the part.
                // Approximate repair limits for parts: Bumper (1 hour), Mouldings (.5 hours), Fender (1 hour), Hood (6 hours), Tailgate (4 hours), Doors (5 hours), Quarter Panels (8 hours), Sill Panels (6 hours)
                // Note: We do not perform paintless dent repair of any type. All damage must be repaired using traditional methods.
                
                "parts_list": [
                    {
                        "part": "Bumper",
                        "position": "FRONT",
                        "s_r": true, // Strip and Refit is required
                        "repair": false, // Repair is not cost effective, damage would exceed 1 hour of repair time
                        "replace": true, // Replacement is required due to the bumper being broken misaligned. Bumpers are low cost parts and are usually replaced if damage exceeds an couple hours of repair time.
                        "paint": true // Painting is required
                    },
                    {
                        "part": "Hood",
                        "position": "",
                        "s_r": true, // Strip and Refit is required
                        "repair": false, // Repair is not possible, damage would exceed 6 hours of repair time
                        "replace": true, // Replacement is required due to severe damage.
                        "paint": true // Painting is required
                    },
                    {
                        "part": "Headlamp",
                        "position": "RH",
                        "s_r": true, // Strip and Refit is required
                        "repair": false, // Repair is not required
                        "replace": true, // Replacement is required due to cracked lens and broken mounting points. 
                        "paint": false // Painting is not required
                    },
                    {
                        "part": "Grille",
                        "position": "FRONT",
                        "s_r": true, // Strip and Refit is required
                        "repair": false, // Repair is not required
                        "replace": true, // Replacement is required since the grille is broken off and missing.
                        "paint": false // Painting is not required
                    },
                    {
                        "part": "Hood Hinges",
                        "position": "",
                        "s_r": true, // Strip and Refit is required
                        "repair": false, // Repair is not required
                        "replace": true, // Replacement is required hood has been shoved far back into the vehicle.
                        "paint": true // Painting is  required
                    },
                    {
                        "part": "Hood Latch",
                        "position": "",
                        "s_r": true, // Strip and Refit is required
                        "repair": false, // Repair is not required
                        "replace": true, // Replacement is required hood has been shoved far back into the vehicle.
                        "paint": false // Painting is not required
                    },
                    {
                        "part": "Fender",
                        "position": "RH",
                        "s_r": true, // Strip and Refit is required
                        "repair": true, // Repair is required since headlamp has been shoved into the fender and has caused minor damage.
                        "replace": false, // Replacement is not required
                        "paint": true // Painting is required
                    }
                    // More parts can be added with the same structure.
                ],

                // "new_parts_info" contains verbatim comments or special instructions 
                // related to new parts needed for the repair job. Include hidden parts (like "Tailgate Latch", "Bumper Absorber", "Bumper Bracket", "Impact Bar", etc.) if they are needed for the repair.
                // Don't forget to include safety critical parts like airbags, seat belts, and suspension components if they are damaged.
                "new_parts_info": "Front Bumper, Hood, RH Headlamp, Front Grille, Hood Hinges, Hood Latch",

                // "specialist_work_required" is an object containing various specialist operations
                // required for the job with boolean indicators (true/false):
                // - "first_dtc": Need for the first Diagnostic Trouble Code.
                // - "wheel_alignment": Requirement for wheel alignment to check and adjust the suspension geometry if needed.
                // - "road_test": Necessity of a road test to ensure vehicle safety and function.
                // - "final_dtc": Requirement for the final Diagnostic Trouble Code after repairs.
                // - "new_part_coding": The need to code new parts into the vehicle's electronic systems, rare for most vehicles.
                // - "air_con": Requirement for servicing the air conditioning system.
                // - "glass_removal": Specialist cleaning of shattered glass from the vehicle's interior.
                // - "adas_calibration": Calibration of Advanced Driver Assistance Systems. This will be evaluated later by a human who is qualified.
                "specialist_work_required": {
                    "first_dtc": true, // A Pre-scan of the vehicle's DTCs is required (always true)
                    "wheel_alignment": false, // A four wheel alignment is not required. (select true when suspension, steering, or drivetrain components are or might be damaged.)
                    "road_test": true, // Road test is required (select true when suspension, steering, or drivetrain components are damaged. Also select true if the vehicle has damage that may have affected the engine, transmission, ADAS functions, etc.)
                    "final_dtc": true, // A Post-scan of the vehicle's DTCs is required (always true)
                    "new_part_coding": false, // New part coding is not required
                    "air_con": false, // Air conditioning service is not required
                    "glass_removal": false, // Glass removal is not required
                    "adas_calibration": false // ADAS calibration is not required
                },

                // "wheels_removed_for_repair" is an object indicating whether each wheel (by position) must be removed for the repair process.
                "wheels_removed_for_repair": {
                    "LF": false, // Removal of Left Front wheel is not required
                    "RF": true, // Removal of Right Front wheel is required
                    "LR": false, // Removal of Left Rear wheel is not required
                    "RR": false  // Removal of Right Rear wheel is not required
                },

                // "smart_repairs_required" is a string field for additional instructions or descriptions of additional suggestions or information for the repair, such as checking if mounting brackets are damaged, consulting the repair methods to determine if a panel is made out of UHSS, checking if any ADAS sensors are damaged, etc.
                "smart_repairs_required": "Check Radiator Support, Condenser, Radiator, LH Headlamp, and LH fender for damage."
            }

            """

            #encode images to base64 for GPT-4-Vision
            def encode_image(image_input):
                # Check if the input is a file path (string) and the file exists
                if isinstance(image_input, str) and os.path.isfile(image_input):
                    with open(image_input, "rb") as image_file:
                        return base64.b64encode(image_file.read()).decode('utf-8')
                # Check if the input is a Streamlit UploadedFile object
                elif hasattr(image_input, 'getvalue'):  # Check if it's a BytesIO instance from an uploaded file
                    return base64.b64encode(image_input.getvalue()).decode('utf-8')
                # Check if the input is a PIL Image object
                elif isinstance(image_input, Image.Image):
                    buffered = io.BytesIO()
                    image_input.save(buffered, format="JPEG")
                    return base64.b64encode(buffered.getvalue()).decode('utf-8')
                else:
                    raise ValueError("Unsupported input type for image encoding")
                
            # Function to scale the costs based on the TradeRetail value, ideally we would use an API connection with parts suppliers
            def scale_costs(trade_retail_value, replacement_costs, scaling_base=4000, slow_scale_factor=0.02):
                trade_retail_value = float(trade_retail_value)  # Convert TradeRetail value to a number

                if trade_retail_value > scaling_base:
                    # Apply a very slow scaling using a square root function
                    # The slow_scale_factor is used to control the rate of scaling further
                    excess_value = trade_retail_value - scaling_base
                    scale_factor = 1 + (slow_scale_factor * math.sqrt(excess_value))
                else:
                    scale_factor = 1  # No scaling if TradeRetail value is £4000 or less

                scaled_costs = {item: cost * scale_factor for item, cost in replacement_costs.items()}
                return scaled_costs

            # Data Packages are "ValuationData" or "VehicleData", this function fetches the data from the UK Vehicle Data API
            def fetch_and_save_data(VRM, DataPackage):
                # Create payload dictionary
                Payload = {
                    "v": 2,  # Package version
                    "api_nullitems": 1,  # Return null items
                    "key_vrm": VRM,  # Vehicle registration mark
                    "auth_apikey": vehicle_data_api_key  # Set the API Key
                }

                # Create GET Request (Include payload & headers)
                r = requests.get(f'https://uk1.ukvehicledata.co.uk/api/datapackage/{DataPackage}', params=Payload)

                # Check for a successful response
                if r.status_code == requests.codes.ok:
                    # Response JSON Object
                    ResponseJSON = r.json()

                    # Extract specific details if DataPackage is ValuationData
                    if DataPackage == "ValuationData":
                        # Navigate through the JSON to extract the required information
                        extracted_data = {
                            "TradeRetail": ResponseJSON["Response"]["DataItems"]["ValuationList"]["TradeRetail"],
                            "StatusCode": ResponseJSON["Response"]["StatusCode"],
                            "Mileage": ResponseJSON["Response"]["DataItems"]["Mileage"],
                            "PlateYear": ResponseJSON["Response"]["DataItems"]["PlateYear"],
                            "VehicleDescription": ResponseJSON["Response"]["DataItems"]["VehicleDescription"]
                        }

                        return extracted_data
                    
                    if DataPackage == "VehicleData":
                        # Navigate through the JSON to extract the required information
                        extracted_data = {
                            "StatusCode": ResponseJSON["Response"]["StatusCode"],
                            "NumberOfDoors": ResponseJSON["Response"]["DataItems"]["TechnicalDetails"]["Dimensions"]["NumberOfDoors"],
                            "KerbWeight": ResponseJSON["Response"]["DataItems"]["TechnicalDetails"]["Dimensions"]["KerbWeight"],
                            "Model": ResponseJSON["Response"]["DataItems"]["ClassificationDetails"]["Dvla"]["Model"],
                            "Make": ResponseJSON["Response"]["DataItems"]["ClassificationDetails"]["Dvla"]["Make"],
                            "IsElectricVehicle": ResponseJSON["Response"]["DataItems"]["ClassificationDetails"]["Ukvd"]["IsElectricVehicle"],
                            "YearOfManufacture": ResponseJSON["Response"]["DataItems"]["VehicleRegistration"]["YearOfManufacture"],
                            "Transmission": ResponseJSON["Response"]["DataItems"]["VehicleRegistration"]["Transmission"],
                            "FuelType": ResponseJSON["Response"]["DataItems"]["VehicleRegistration"]["FuelType"],
                            "BodyStyle": ResponseJSON["Response"]["DataItems"]["SmmtDetails"]["BodyStyle"]
                        }

                        return extracted_data

                else:
                    # Request was not successful
                    ErrorContent = f'Status Code: {r.status_code}, Reason: {r.reason}'
                    print(ErrorContent)

            # Function to send images to GPT-4-Vision
            def send_images_to_gpt4(example_images, images, system_prompt, user_prompt, openai_api_key):

                headers = {
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {openai_api_key}"
                }

                base64_images = [encode_image(image) for image in images]
                if example_images:
                    base64_example_images = [encode_image(image) for image in example_images]
                    base64_images.extend(base64_example_images)

                payload = {
                    "model": "gpt-4-vision-preview",
                    "messages": [
                        {
                            "role": "system",
                            "content": system_prompt
                        },
                        {
                            "role": "user",
                            "content": [
                                *[
                                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image}"}} for image in base64_images
                                ],
                                {"type": "text", "text": user_prompt}
                            ]
                        }
                    ],
                    "max_tokens": 4000,
                    "temperature" : 0
                }

                # Initialize an empty list to store the responses
                responses = []

                response = requests.post('https://api.openai.com/v1/chat/completions', headers=headers, json=payload)

                if response.status_code == 200:
                    # Append successful response to the list
                    responses.append(response.json()['choices'][0]['message']['content'])
                    return response.json()['choices'][0]['message']['content']
                else:
                    print("Failed to process the image")
                    # Optionally append an error message or handle the error as needed
                    responses.append({'error': 'Failed to process the image'})
                    return {"error": f"Request failed with status code {response.status_code}"}



            # Function for natural language prompts only, can use GPT-3.5 or GPT-4
            def gpt_turbo_chat(model, system_prompt, user_prompt, openai_api_key):
                headers = {
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {openai_api_key}"
                }

                payload = {
                    "model": f"{model}",
                    "messages": [
                        {
                            "role": "system",
                            "content": system_prompt
                        },
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": user_prompt}
                            ]
                        }
                    ],
                    "max_tokens": 1000,
                    "temperature" : 0
                }

                response = requests.post('https://api.openai.com/v1/chat/completions', headers=headers, json=payload)
                
                if response.status_code == 200:
                    return response.json()['choices'][0]['message']['content']
                else:
                    print("Failed to process the image")
                    return {"error": f"Request failed with status code {response.status_code}"}


            with st.spinner('Fetching Vehicle Valuation...'):
                valuation_data_response = fetch_and_save_data(vehicle_reg, "ValuationData")

                trade_retail = valuation_data_response["TradeRetail"]
                scaled_costs = scale_costs(trade_retail, replacement_costs)
                print(scaled_costs)



            # For gathering VehicleData
            with st.spinner('Fetching Vehicle Data...'):
                Car_data_response = fetch_and_save_data(vehicle_reg, "VehicleData")
            print(Car_data_response)

            make_model = Car_data_response["Make"] + " " + Car_data_response["Model"]
            st.write(f"Vehicle Identified from Database: {make_model}")
            
            st.write(f"Pre-Accident Value: £{trade_retail}")
            st.write("")

            example_images = ""



            #Time for the cool stuff!


            #First we need to determine the damage location
            system_prompt = f"""You are assisting and Accident Repair group by identifying the damage location on vehicles.
            You will be shown various images of a {make_model}, you must determine whether the overall damage is located at the front or rear of the vehicle.

            Provide your output as either "Front" or "Rear" with no other text. Provide only one output for the overall vehicle/damages.
            """

            user_prompt = "Identify the location of the damage on the vehicle from the options provided."
            example_images = ""


            with st.spinner('Determining Damage Location in Images...'):
                front_rear = send_images_to_gpt4(example_images, images, system_prompt, user_prompt, openai_api_key)
                print(front_rear)



                system_prompt = f"""You are assisting and Accident Repair group by identifying the damage location on vehicles.
                You will be shown images of a {make_model}, and you must choose which of the following best describes the location of the damage on the vehicle: Right Front, Left Front, Right Rear, Left Rear, Front, Rear, Right, Left

                Your output should be only one of the options from the list above. Provide that and no other text.
                """

                user_prompt = "Identify the location of the damage on the vehicle from the options provided."

                print("Now to determine the location")
                damage_location_part1 = send_images_to_gpt4(example_images, images, system_prompt, user_prompt, openai_api_key)
                print(damage_location_part1)


                #Turning GPT-4 weakness into a strength! Its terrible at lefts and right so I just let it do its thing and use some logic to correct if needed
                if front_rear == "Front":
                    system_prompt = f"""You are assisting and Accident Repair group by identifying the damage location on vehicles.
                    You will be shown various images of a {make_model}, you must determine if images exist for both the front and rear of the vehicle.

                    Provide your output as either "Yes" or "No" with no other text. Provide only one output that accounts for all the images.
                    """

                    user_prompt = "Identify the location of the damage on the vehicle from the options provided."
                    example_images = ""

                    front_and_rear = send_images_to_gpt4(example_images, images, system_prompt, user_prompt, openai_api_key)

                    if front_and_rear == "No":
                        system_prompt = "You are assisting with some data cleaning for a researcher. You must switch 'Left' to 'Right' and vice versa if the damage_location_part1 value the user provides you is 'Front'. Otherwise, output the damage location unchanged. Provide only one output for the overall vehicle/damages. If the damage_location_part1 is only Front or Rear, output the damage_location_part1 unchanged."
                        user_prompt = f"Here is the front_rear value: {front_rear}. Here is the damage_location_part1 value: {damage_location_part1}. Provide the output based on the rules you've been provided."

                        print("now to determine the correct location based on industry standards")
                        model = "gpt-3.5-turbo-0125"
                        damage_location = gpt_turbo_chat(model, system_prompt, user_prompt, openai_api_key)
                        
                        st.write("Damage Location in Images: ", damage_location)
                        st.write("")
                    else:
                        st.write(f"Damage Location in Images: {damage_location_part1}")
                        st.write("")
                        damage_location = damage_location_part1
                else:
                    st.write(f"Damage Location in Images: {damage_location_part1}")
                    st.write("")
                    damage_location = damage_location_part1




            #Now that we know where the damage is in the photos we need to compare it to the claim and vehicle details to check for fraud

            example_images = ""

            system_prompt = f"""You are assisting and Accident Repair group and insurance company by doing some basic fraud checks.
            Start with Fraud detection/confirmation that the vehicle seems to be a {make_model}.
            Next check that the images are not of a computer screen, a printed image, or contain any watermarks.
            Finally you must compare the damage location provided in the FNOL with the damage location identified by another expert.
            If anything indicates this might be fraudulent (or if the vehicle does not seem to be assessable given the images) the process should stop and the recommendation should be to escalate this to a senior.

            Provide your output as JSON in the following format, with the fraudulent key set to True or False:
            {{"fraudulent": False, "Description": "The images are of the correct vehicle and do not contain any watermarks or signs of tampering."}}

            This will all be evaluated by a human, so if you are unsure, please flag it as potentially fraudulent.
            """
            user_prompt = f"Examine the images closely and provide your outputs as JSON. Here is the FNOL description: {FNOL_description}, and the damage location identified by another expert is {damage_location}"


            with st.spinner('Checking for Fraudulent Activity...'):
                response = send_images_to_gpt4(example_images, images, system_prompt, user_prompt, openai_api_key)

                system_prompt = "You must parse the input you are provided and return valid json with no backticks or markdown."
                user_prompt = f"Provide the raw json for the following: {response}"

                model = "gpt-3.5-turbo-0125"
                good_json = gpt_turbo_chat(model, system_prompt, user_prompt, openai_api_key)
                

                # Check if good_json is not None and is a non-empty string
                if good_json:
                    try:
                        # Parse the JSON string into a Python dictionary
                        parsed_json = json.loads(good_json)
                        

                        # Now you can check if 'fraudulent' is True (Python's False since it's 'false' in the JSON) and print the description
                        if parsed_json.get('fraudulent', False):
                            st.write(f"⚠️ Fraud detected: {parsed_json['Description']}")
                        else:
                            st.write("✅ No fraud detected")
                            
                    except json.JSONDecodeError as e:
                        st.write(f"Failed to decode JSON: {e}")
                else:
                    st.write("Failed to get a valid response or good_json is None or an empty string")



            #Fraud checks are all done, now we need to create the repair plan


            formatted_context = f"""
                        "Here is some additional information about this vehicle/claim:\n"
                        {FNOL_description}\n
                        "It is vital that you consider this information when creating your repair plan. Keep in mind that this may not be all the information you need to create a repair plan, so examine the images carefully."
                    """

            system_prompt = """
            You are an expert vehicle damage assessor working with team members at Halo ARC Ltd to create a repair plan for a vehicle that has been involved in an accident.
            You will be given three images and a sample repair plan for a VW Golf, use this as a guide when creating your own.
            The goal is to create an initial repair plan meeting BS 10125 Standards that can be used to order parts and set the site up for the repair. This is just a test, and will be evaluated by a human who is qualified.
            Your repair plan will be graded on the following categories:
            Description accuracy - How in-depth and accurate you describe the damage in the images. Points are deducted if you fail to include visible damage, even if the component only requires further inspection.
            Collision Repair standards - How well you abide by industry standards and regulation (BS 10125) when creating the repair plan. Failure to include safety critical operations will result in a loss of points.
            Repair Versus Replace Accuracy - Points will be deducted from this if you choose to repair a panel above the repair threshold. They are also deducted if you replace a panel for no reason, but this is less severe.
            Special Considerations - You can gain points here by providing appropriate insights and reccomendations specific to the repair for the body shop to consider.

            You will get a tip based on your performance (up to $200) so take your time and think through the different steps methodically.
            Your output must be in the structured JSON format.
            """

            user_prompt = f"""
            I am a qualified vehicle damage assessor and I will be evaluating your repair plan before it is used in any real world scenarios.
            Below is an example of the JSON format to follow, this example has been created from the VW Golf in the first three images you will be shown.
            {json_example}

            Your task is to create a repair plan for the next vehicle you will be shown.
            {formatted_context}
            Focus on damage you can clearly see. Explain waht you see and lay out your plan in the "damage_description" field. This entry in the JSON job card is there for you to show your work, so be as detailed as possible.
            Any missed items or operations will be deducted from your score, as will any unnecessary items. Use your understanding of current repair standards to guide you.
            Remember, you lose more points for including unnecessary or incorrect items than you do for missing items. You are also penalised if you choose to replace a part that can be repaired.
            Respond with only the structured JSON repair plan and nothing else.
            """

            example_images = ["GOLF (1).jpg", "GOLF (4).jpg", "GOLF (7).jpg"]  # List of image file paths

            with st.spinner('Creating Repair Plan...'):
                repair_plan = send_images_to_gpt4(example_images, images, system_prompt, user_prompt, openai_api_key)
                             
                # Remove any non-JSON compliant parts from the string (like Python comments)
                json_data = repair_plan.split('\n')
                json_data = [line for line in json_data if not line.strip().startswith('//')]
                json_data = "\n".join(json_data)

                # Remove any leading 'json' keyword and strip any remaining whitespace or special characters
                json_data = json_data.strip('` \n')

                if json_data.startswith('json'):
                    json_data = json_data[4:]  # Remove the first 4 characters 'json'

                try:
                    # Parse the JSON data
                    data = json.loads(json_data)
                    
                except json.JSONDecodeError as e:
                    st.write(f"Failed to decode JSON: {e}")


                    #If Repair plan wasnt good JSON then try again


                    repair_plan = send_images_to_gpt4(example_images, images, system_prompt, user_prompt, openai_api_key)
                    # Remove any non-JSON compliant parts from the string (like Python comments)
                    json_data = repair_plan.split('\n')
                    json_data = [line for line in json_data if not line.strip().startswith('//')]
                    json_data = "\n".join(json_data)

                    # Remove any leading 'json' keyword and strip any remaining whitespace or special characters
                    json_data = json_data.strip('` \n')

                    if json_data.startswith('json'):
                        json_data = json_data[4:]  # Remove the first 4 characters 'json'

                    # Parse the JSON data
                    data = json.loads(json_data)
                    


                job_card = f"Digital Job Card for Vehicle: {data['reg_no']}\n\n"

                # Damage description
                job_card += f"Damage Description: {data['damage_description']}\n\n"

                # Adding parts list
                job_card += "Parts List:\n"
                for part in data['parts_list']:
                    job_card += f"  - {part['part']} ({'Position: ' + part['position'] if part['position'] else 'Position: N/A'}): "
                    actions = []
                    if part.get('s_r', False):
                        actions.append("Strip & Refit")
                    if part.get('repair', False):
                        actions.append("Repair")
                    if part.get('replace', False):
                        actions.append("Replace")
                    if part.get('paint', False):
                        actions.append("Paint")
                    job_card += ", ".join(actions) + "\n"

                # New parts information
                job_card += f"\nNew Parts Info:\n  {data['new_parts_info']}\n"

                # Specialist work required
                job_card += "\nSpecialist Work Required:\n"
                for key, value in data['specialist_work_required'].items():
                    if value:
                        job_card += f"  - {key.replace('_', ' ').title()}\n"

                # Wheels removed for repair
                job_card += "\nWheels Removed for Repair:\n"
                for wheel, removed in data['wheels_removed_for_repair'].items():
                    job_card += f"  - {wheel}: {'Removed' if removed else 'Not Removed'}\n"

                # Smart repairs required
                job_card += f"\nSmart Repairs Required:\n  {data['smart_repairs_required']}"
                st.write("")
                st.write(job_card)
                st.write("")



            #Repair plan is done, now to calculate the cost
                

            system_prompt = "You must use the dictionary and repair plan to create the overall cost of the repair. Take your time and work through the problem to ensure you have the coorect cost."
            user_prompt = f"Provide the overall cost for the following repair plan: {repair_plan}\n Here is the dictionary of costs: {scaled_costs}. You must only use the full cost for replacement parts, if a part is repaired you should use half of the dictionary cost."

            model = "gpt-4-turbo-preview"
            
            with st.spinner('Calculating Repair Costs...'):
                costs = gpt_turbo_chat(model, system_prompt, user_prompt, openai_api_key)
                

                #Now to extract the cost from the response

                system_prompt = "You must provide the cost of the repair as a number with no currency symbol or commas."
                user_prompt = f"Provide the numerical cost for the following: {costs} Do not include any currency symbols and only use two decimal places. Provide no additional text."

                
                model = "gpt-3.5-turbo-0125"
                cleaned_cost = gpt_turbo_chat(model, system_prompt, user_prompt, openai_api_key)
                st.write(f"The cost of the repair is: £{cleaned_cost}")
                st.write("")



            #Now for the Drivability check

            example_images = ""

            system_prompt = """
            You are an expert vehicle damage assessor working with team members at Halo ARC Ltd to triage a vehicle that has been involved in an accident.
            You will be given a description of the damage and a repair plan as well as image of the vehicle. Your task is to determine if the vehicle is safe to drive

            This is just a test, and will be evaluated by a human who is qualified.

            If any of the following are true, the vehicle is not safe to drive:
            Any SRS or safety component Deployed (e.g. Airbags)
            Suspension, wheel, or tyre severely damaged
            Jagged edges/large tears in the metal
            Vehicle does not lock
            Vehicle does not drive
            Any lamp lens shattered
            Missing exterior panels (e.g. bumper torn off)
            Mirror glass damaged or housing not intact
            Radiator or Condenser visibly damaged and leaking
            Customer reporting warning lights on the dash (related to accident)
            Exhaust damage that causes excessive noise or fumes
            Engine or transmission not working correctly
            EV Vehicle with underside or High voltage component damage
            Glass shattered or cracked

            Make no assumptions and only use the information provided to you. If it hasn't been listed on the job card you should not consider it when determining drivability.
            Mentions on the job card to check components do not suffice as evidence to deem the car non-drivable.

            Your output must be in the structured JSON format as shown in the examples below:
            example 1: {"drivable": true, "reason": "The vehicle is safe to drive."}
            example 2: {"drivable": false, "reason": "The vehicle is not safe to drive due to the airbags being deployed and the windscreen being shattered."}
            example 3: {"drivable": false, "reason": "The vehicle is not safe to drive due to the severe wheel damage and the suspension damage."}
            """

            user_prompt = f"""
            I am a qualified vehicle damage assessor and I will be evaluating you.
            Here is the repair plan for the {make_model}.
            {repair_plan}

            {formatted_context}

            Using this and the images you have been provided evaluate the drivability of the vehicle and provide your response as JSON.
            """

            

            with st.spinner('Assessing Drivability...'):
                drivability_output = send_images_to_gpt4(example_images, images, system_prompt, user_prompt, openai_api_key)
                


                #now turn the output into valid json

                system_prompt = "You must parse the input you are provided and return valid json with no backticks or markdown."
                user_prompt = f"Provide the raw json for the following: {drivability_output}"

                
                model = "gpt-3.5-turbo-0125"
                good_drivability = gpt_turbo_chat(model, system_prompt, user_prompt, openai_api_key)
                

                # Check if good_drivability is not None and is a non-empty string
                if good_drivability:
                    try:
                        # Parse the JSON string into a Python dictionary
                        parsed_json = json.loads(good_drivability)
                        print(parsed_json)

                        # Now you can check if 'drivable' is True (Python's False since it's 'false' in the JSON) and print the reason
                        if parsed_json.get('drivable', False):
                            st.write("✅ The vehicle is safe to drive.")
                        else:
                            st.write("❌ The vehicle is not safe to drive.")
                            st.write(parsed_json['reason'])
                    except json.JSONDecodeError as e:
                        st.write(f"Failed to decode JSON: {e}")
                else:
                    st.write("Failed to get a valid response or good_drivability is None or an empty string")

                st.write("")

            
            #Now for the Triage and Allocation
            system_prompt = f"""
            You are an expert vehicle damage assessor working with team members at Halo ARC Ltd to triage a vehicle that has been involved in an accident.
            You will be given a description of the damage and a repair plan as well as images of the vehicle. Your task is to determine if the vehicle should be sent to a spoke site, a hub site, or escalated for a total loss assessment.

            This is just a test, and will be evaluated by a human who is qualified.

            First you must determine if the repair costs are high enough for the vehicle to be sent for a total loss assessment, or if it can be booked to the correct repair location.
            To do this, compare the trade retail valuation with the overall repair cost. If the repair cost is 60% or more of the vehicle value it must be escalated as a possible total loss.
            The vehicle value: {trade_retail}
            The repair cost: {cleaned_cost}

            If the repairs are within the threshold you may proceed with determing the location it should go to.

            The following is a guide to help you determine which repairs should go to hubs:

            Any SRS or safety component Deployed (e.g. Airbags)
            Significant suspension damage
            Welded on panels requiring replacement (e.g. Quarter panel, roof, structural rails)
            Engine or transmission not working correctly
            EV Vehicle with underside or High voltage components damaged
            Excessively Large repairs (e.g. replacement of all panels on the side of a car, damage deep into the engine bay, boot floor replacements)
            Obvious Radiator support damaged

            As a general guide, most other repairs can be done at spoke sites.

            Make no assumptions and only use the information provided to you.

            Think carefully about all of the damages and provide a thorough explanation for your decision.
            """

            user_prompt = f"""
            I am a qualified vehicle damage assessor and I will be evaluating your decision.
            Here is the repair plan for the {make_model}.
            {repair_plan}

            {formatted_context}

            Determine if the vehicle should go to total loss, a spoke site, or a hub site based on the information provided.
            """
            

            
            with st.spinner('Triaging and Allocating...'):
                triage = send_images_to_gpt4(example_images, images, system_prompt, user_prompt, openai_api_key)
                

                #now turn the output into valid json


                system_prompt = "You are assisting a researcher by cleaning data on collision repair. You will be provided a verbose explanation, and you must provide only the final decsion from the following options: Total Loss, Hub Site, Spoke Site. Provide no additional text."
                user_prompt = f"Provide the decsion for the following: {triage} Use only the final recommendation from the three possible options. Provide no additional text."

                model = "gpt-3.5-turbo-0125"
                triage_decision = gpt_turbo_chat(model, system_prompt, user_prompt, openai_api_key)
                

                # Check the decision and display the appropriate message
                try:
                    if triage_decision == "Hub Site" or triage_decision == "Spoke Site":
                        st.write(f"✅ This vehicle should go to a {triage_decision}")
                    elif triage_decision == "Total Loss":
                        st.write(f"⚠️ This vehicle should be escalated to a {triage_decision} assessment")
                    else:
                        print("Invalid decision or decision not found in response.")
                except json.JSONDecodeError as e:
                    print(f"Failed to decode JSON: {e}")




                system_prompt = "You are assisting with a researcher cleaning up data from the collision repair industry. You must summarise the input to help the researcher understand if the vehicle should go to a hub site, a spoke site, or be asssessed as a possible total loss. You should explicitly mention the repair cost percentage of the vehicle value and the reason for the decision. Use no more than 3 sentences. Use markdown formatting to make it as easy to read as possible."
                user_prompt = f"Provide the short, digestable version of the following: {triage}."

                
                model = "gpt-3.5-turbo-0125"
                triage_short = gpt_turbo_chat(model, system_prompt, user_prompt, openai_api_key)
                st.write(triage_short)
                st.write("")


            #All done! Now time for shameless self promotion :D

            # Path to the Halo ARC Logo
            haloarc_logo_path = 'cropped_image_wider.jpg'  # Update this to the path where your QR code image is stored

            # Path to the QR code image
            qr_code_image_path = 'haloarc_job_link_qr.png'  # Update this to the path where your QR code image is stored

            # Create a 3-column layout (left, center, right)
            col1, col2 = st.columns([1,1])
            
            with col1:
                st.image(haloarc_logo_path, caption="", use_column_width=True)

            # Use the middle column to display the QR code centered
            with col2:
                # Centering the image in the column
                st.image(qr_code_image_path, use_column_width=True)


            # Use Markdown with HTML to customize the caption text
            st.markdown("""
                <style>
                .big-font {
                    font-size:20px;  # Increased font size for better readability
                    font-weight:bold;  # Keeps the text bold for emphasis
                    line-height:1.5;  # Adds more space between lines for easier reading
                }
                .center-text {
                    text-align: center;  # Ensures text is centered
                    margin-top: 20px;  # Adds space above the text block for better layout
                    margin-bottom: 20px;  # Adds space below the text block for better layout
                }
                </style>
                <div class='center-text'>
                    <p class='big-font'>Join me in revolutionising a neglected industry!<br>We're looking for talented people with that special Spark!</p>
                </div>    
                """, unsafe_allow_html=True)


if __name__ == "__main__":
    display_page()  # If thing then do the thing