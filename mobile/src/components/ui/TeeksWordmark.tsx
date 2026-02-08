import React from 'react';
import { SvgXml } from 'react-native-svg';
import { Colors } from '../../theme/Theme';

interface TeeksWordmarkProps {
    color?: string;
    width?: number;
    height?: number;
}

const getWordmarkSvg = (textColor: string) => `
<svg width="600" height="150" viewBox="0 0 600 150" fill="none" xmlns="http://www.w3.org/2000/svg">
  <g transform="translate(20, 25) scale(0.25)">
    <path d="M80 100C80 88.9543 88.9543 80 100 80H230V150H80V100Z" fill="#7E2E2E"/>
    <path d="M245 80H300C311.046 80 320 88.9543 320 100V150H245V80Z" fill="#D97745"/>
    <path d="M165 165H235V300C235 311.046 226.046 320 215 320H185C173.954 320 165 311.046 165 300V165Z" fill="#7E2E2E"/>
  </g>
  <text x="130" y="105" font-family="serif" font-weight="600" font-size="80" fill="${textColor}" letter-spacing="-2">Teeks<tspan fill="#D97745">.</tspan></text>
</svg>
`;

export const TeeksWordmark: React.FC<TeeksWordmarkProps> = ({
    color = Colors.textPrimary,
    width = 300,
    height = 75,
}) => {
    return (
        <SvgXml
            xml={getWordmarkSvg(color)}
            width={width}
            height={height}
        />
    );
};
