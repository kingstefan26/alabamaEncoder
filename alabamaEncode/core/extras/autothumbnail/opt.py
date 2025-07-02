class autothumbnailOptions:
    def __init__(
        self,
        input_file: str = "",
        output_folder: str = "",
        skip_result_image_optimisation=False,
        detect_faces=False,
        only_face_frames=False,
        use_face_frequency=False,
    ):
        self.input_file = input_file
        self.output_folder = output_folder
        self.skip_result_image_optimisation = skip_result_image_optimisation
        self.detect_faces = detect_faces
        self.only_face_frames = only_face_frames
        self.use_face_frequency = use_face_frequency
