using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;

namespace beholder_configuration_app.Models
{
    public class CameraCardControls
    {
        public Border Card { get; set; } = null!;
        public Label ActiveLabel { get; set; } = null!;
        public BoxView ActiveIndicator { get; set; } = null!;
        public Picker RowPicker { get; set; } = null!;
        public Picker SlotPicker { get; set; } = null!;
        public Button ActiveButton { get; set; } = null!;
        public Image IdentifyImage { get; set; } = null!;

        public bool UpdatingFromStatus { get; set; }
        public bool UserEditingSlot { get; set; }
    }
}
