import axios from "axios";
import Button from '@mui/material/Button';

// Change status of ticket to archived
function handleArchive(id: number) {
    axios.put(`http://localhost:8000/tickets/${id}/status?status=archived`)
    window.location.reload();
}

export default function CloseButton(props: { id: number }) {

    return (
        <Button
            variant="outlined"
            color="success"
            onClick={() => handleArchive(props.id)}
        >
            I fix it !
        </Button>
    )
}