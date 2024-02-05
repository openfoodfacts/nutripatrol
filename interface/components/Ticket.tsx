import Paper from '@mui/material/Paper';
import { styled } from '@mui/material/styles';
import Date from '../components/Date'
import CloseButton from '../components/CloseButton'
import ArchiveButton from '../components/ArchiveButton'
import BarcodeButton from '../components/BarcodeButton'

const Item = styled(Paper)(({ theme }) => ({
    backgroundColor: theme.palette.mode === 'dark' ? '#1A2027' : '#fff',
    ...theme.typography.body2,
    padding: theme.spacing(1),
    textAlign: 'center',
    color: theme.palette.text.primary,
  }));

export default function Ticket({ticket}: any) {
    
    return (
        <Item>
            <div className='ticket-container'>
                
                <div style={{ display: 'flex', gap: '10px', alignItems: 'center'}}>
                    <img 
                        src={ticket.url} 
                        // src='https://images.openfoodfacts.net/images/products/327/408/000/5003/1.400.jpg'
                        alt={ticket.barcode}
                        width={100}
                        height={100}
                    />
                </div>
                <Date created_at={ticket.created_at} />
                <div style={{ display: 'flex', gap: '30px' }}>
                    <BarcodeButton barcode={ticket.barcode} />
                    <CloseButton id={ticket.id} />
                    <ArchiveButton id={ticket.id} />
                </div>
            </div>
        </Item>
    )
}