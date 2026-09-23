namespace beholder_configuration_app.Services.WebServices
{
    public enum APIEndpoint
    {
        SystemGetStatus,

        ProjectGetAll,
        ProjectGetCurrent,
        ProjectCreate,
        ProjectOpen,
        ProjectClose,
        ProjectDelete,
        ProjectTransferManifest,
        ProjectTransferFile,

        CameraGetAll,
        CameraEnable,
        CameraDisable,
        CameraSetSlot,
        CameraIdentify,

        CaptureSetSingleMode,
        CaptureSetAutomaticMode,
        CaptureSetAutomaticInterval,
        CaptureGetStatus,
        CaptureTrigger
    }
}