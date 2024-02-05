import axios from "axios";
import Button from '@mui/material/Button';


// Change status of ticket to closed
function handleClose(id: number) {
    axios.put(`${import.meta.env.VITE_API_URL}/tickets/${id}/status?status=closed`)
    window.location.reload();
}

export default function CloseButton(props: { id: number }) {

    return (
        <Button
            variant="outlined"
            color="error"
            onClick={() => handleClose(props.id)}
        >
            No problem
        </Button>
    )
}