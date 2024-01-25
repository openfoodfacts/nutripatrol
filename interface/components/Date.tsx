function dateParser(date: string) {
    // Take only the date and hour and minutes
    let newDate = date.slice(0, 16).split('T').join(' / ')
    return newDate
}

export default function Date(props: any){
    return (
        <p>{dateParser(props.created_at)}</p>
    )
}