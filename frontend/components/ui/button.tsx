import * as React from 'react';
import {Slot} from '@radix-ui/react-slot';
import {cva} from 'class-variance-authority';
import {cn} from '../../lib/utils';
const variants = cva('button', {variants:{variant:{default:'primary',outline:'outline'}} ,defaultVariants:{variant:'default'}});
export function Button({className,variant='default',asChild=false,...props}:React.ButtonHTMLAttributes<HTMLButtonElement>&{variant?:'default'|'outline';asChild?:boolean}) {const Comp=asChild?Slot:'button';return <Comp className={cn(variants({variant}),className)} {...props}/>}
