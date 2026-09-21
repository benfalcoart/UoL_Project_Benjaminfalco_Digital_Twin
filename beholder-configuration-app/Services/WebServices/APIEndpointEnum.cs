namespace beholder_configuration_app.Services.WebServices
{
    public enum APIEndpoint
    {
        SystemGetStatus,

        ProjectCreate,

        CameraGetAll,
        CameraEnable,
        CameraDisable,

        CaptureSetSingleMode,
        CaptureSetAutomaticMode,
        CaptureSetAutomaticInterval,
        CaptureGetStatus,
        CaptureTrigger
    }
}