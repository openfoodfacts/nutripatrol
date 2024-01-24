// Layout Menu Component
import AppBar from '../AppBar'

export default function LayoutMenu({ children }: any) {
  return (
    <div className='main-container'>
        <AppBar />
        { children }
    </div>
  );
}