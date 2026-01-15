CATIA detections of words, zones and icons

app_v3.py: saves annotated image as 'result_labeled.png' and labels as 'result_info.json'. It is inherited from Microsoft OmniParserV2 but the caption by VLM 'Florence2' and the web app module 'gradio' are deactivated.

util/ consists of the files with functions imported by app_v3.py.

detect_selected.py: returns coordinates of bounding box (x1, y1, x2, y2) of the orange selected items (tree on the left or parts on the right), using cv2.findContours.

feature_mapping.py: finds the location of an icon in Teamcenter, using SIFT and FLANN.

find_flag2.py: is used to find the latest release in Teamcenter, using cv2.matchTemplate.

ocr.py: returns the coordinate of center point of the words matched with user query, using PaddleOCR.

part_bbox.py: returns the coordinates of bounding box (x1, y1, x2, y2) of the displayed part in the center of CATIA UI, using cv2.

The following files are related to customized YOLO models.

generate_dataset3.py: generates the dataset used for training and test. It loads the icons and pastes them randomly on a background in a tight layout. Accordingly, the labels are automatically generated, given the location and size of each pasted icon.

train.py: launches the training.

test.py: launches the test.

inference.py: visualizes the inference of a model on an original screenshot of CATIA UI.

dataset3/ is the location of dataset for YOLO.

figures/ includes the icons for generating dataset and screenshots for testing results.

models/ contains the YOLO models from Microsoft OmniParser V2 and Ultralytics.

result/ contains the visulizations of the python files in the whole project.

runs/ saves the result of training and testing including models.

