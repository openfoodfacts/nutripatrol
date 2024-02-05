import Button from '@mui/material/Button';
import { Link } from 'react-router-dom';

export default function LoginPage() {
    return (
        <div style={{position: "absolute", width: "100vw", height: "100vh", zIndex: "-10", color: '#281900', display: 'flex',flexDirection: "column", alignItems: "center", justifyContent:"center"}}>
            <h2 style={{fontSize: '1.4rem', margin: "2rem 0"}}>🇫🇷 Connectez-vous avec votre compte OpenFoodFacts </h2>
            <h2 style={{fontSize: '1.4rem', margin: "2rem 0"}}>🇺🇸 / 🇬🇧 Login with your OpenFoodFacts account </h2>
            <Button 
                component={Link} 
                to={`${import.meta.env.VITE_PO_URL}/cgi/session.pl`} 
                variant='contained'
                color="primary"
                target="_blank" >
                Login
            </Button>
        </div>
    )
}