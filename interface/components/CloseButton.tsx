import axios from "axios";
import Button from '@mui/material/Button';


// Change status of ticket to closed
function handleClose(id: number) {
    axios.put(`http://localhost:8000/tickets/${id}/status?status=closed`)
    window.location.reload();
}

export default function CloseButton(props: { id: number }) {

    return (
        <Button
            color="error"
            onClick={() => handleClose(props.id)}
        >
            Close
        </Button>
    )
}