import Button from '@mui/material/Button';
import { Link } from 'react-router-dom';

export default function BarcodeButton(props: { barcode: string }) {
    const linkUrl = `https://world.openfoodfacts.org/cgi/product.pl?type=edit&code=${props.barcode}`;

    return (
        <Button 
            component={Link} 
            to={linkUrl} 
            variant='contained'
            color="primary"
            target="_blank" >
            Edit
        </Button>
    );
}