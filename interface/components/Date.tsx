function dateParser(date: string) {
    // Take only ten first caracters of the date
    let newDate = date.slice(0, 10).split('-').reverse().join('/')
    return newDate
}

export default function Date(props: any){
    return (
        <p>{dateParser(props.created_at)}</p>
    )
}