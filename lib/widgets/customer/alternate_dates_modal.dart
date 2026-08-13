import 'package:flutter/material.dart';
import 'package:intl/intl.dart';

class AlternateDatesModal extends StatefulWidget {
  final DateTime requestedDate;
  final List<DateTime> alternateDates;
  final Map<String, dynamic> capacityInfo;
  final Function(DateTime?) onDateSelected;

  const AlternateDatesModal({
    super.key,
    required this.requestedDate,
    required this.alternateDates,
    required this.capacityInfo,
    required this.onDateSelected,
  });

  @override
  State<AlternateDatesModal> createState() => _AlternateDatesModalState();
}

class _AlternateDatesModalState extends State<AlternateDatesModal> {
  DateTime? selectedAlternate;

  @override
  Widget build(BuildContext context) {
    final ordersCount = widget.capacityInfo['ordersCount'] ?? 0;
    final capacity = widget.capacityInfo['capacity'] ?? 10;
    final percentFull = widget.capacityInfo['percentFull'] ?? 0;

    return Container(
      decoration: const BoxDecoration(
        color: Color(0xFFFFFDF8),
        borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          // Handle
          Container(
            margin: const EdgeInsets.only(top: 12),
            width: 40,
            height: 4,
            decoration: BoxDecoration(
              color: const Color(0xFFB05E27).withOpacity(0.3),
              borderRadius: BorderRadius.circular(2),
            ),
          ),

          // Header
          Padding(
            padding: const EdgeInsets.all(20),
            child: Column(
              children: [
                Container(
                  padding: const EdgeInsets.all(16),
                  decoration: BoxDecoration(
                    color: const Color(0xFFFEF3C7),
                    borderRadius: BorderRadius.circular(16),
                  ),
                  child: Row(
                    children: [
                      Icon(
                        percentFull >= 100
                            ? Icons.event_busy
                            : Icons.warning_amber_rounded,
                        color: const Color(0xFFB05E27),
                        size: 32,
                      ),
                      const SizedBox(width: 12),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              percentFull >= 100 ? 'Baker Fully Booked' : 'Baker Nearly Full',
                              style: const TextStyle(
                                fontSize: 16,
                                fontWeight: FontWeight.bold,
                                color: Color(0xFF451A03),
                              ),
                            ),
                            const SizedBox(height: 4),
                            Text(
                              'This baker has $ordersCount of $capacity orders on ${DateFormat('MMM d').format(widget.requestedDate)}',
                              style: const TextStyle(
                                fontSize: 13,
                                color: Color(0xFF92400E),
                              ),
                            ),
                          ],
                        ),
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: 16),
                const Text(
                  'Choose an alternate date with availability:',
                  style: TextStyle(
                    fontSize: 14,
                    fontWeight: FontWeight.w600,
                    color: Color(0xFF451A03),
                  ),
                ),
              ],
            ),
          ),

          // Alternate dates list
          if (widget.alternateDates.isEmpty)
            Padding(
              padding: const EdgeInsets.symmetric(vertical: 20),
              child: Text(
                'No alternate dates available in next 2 weeks',
                style: TextStyle(
                  fontSize: 13,
                  color: const Color(0xFF451A03).withOpacity(0.6),
                ),
              ),
            )
          else
            ListView.builder(
              shrinkWrap: true,
              physics: const NeverScrollableScrollPhysics(),
              padding: const EdgeInsets.symmetric(horizontal: 20),
              itemCount: widget.alternateDates.length,
              itemBuilder: (context, index) {
                final date = widget.alternateDates[index];
                final isSelected = selectedAlternate == date;
                final dayName = DateFormat('EEEE').format(date);
                final dateStr = DateFormat('MMM d, yyyy').format(date);

                return GestureDetector(
                  onTap: () {
                    setState(() {
                      selectedAlternate = date;
                    });
                  },
                  child: Container(
                    margin: const EdgeInsets.only(bottom: 12),
                    padding: const EdgeInsets.all(16),
                    decoration: BoxDecoration(
                      color: isSelected
                          ? const Color(0xFFB05E27)
                          : Colors.white,
                      borderRadius: BorderRadius.circular(12),
                      border: Border.all(
                        color: isSelected
                            ? const Color(0xFFB05E27)
                            : const Color(0xFFD4A574),
                        width: 1.5,
                      ),
                    ),
                    child: Row(
                      children: [
                        Icon(
                          isSelected
                              ? Icons.radio_button_checked
                              : Icons.radio_button_unchecked,
                          color: isSelected
                              ? Colors.white
                              : const Color(0xFFB05E27),
                          size: 24,
                        ),
                        const SizedBox(width: 12),
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(
                                dayName,
                                style: TextStyle(
                                  fontSize: 15,
                                  fontWeight: FontWeight.bold,
                                  color: isSelected
                                      ? Colors.white
                                      : const Color(0xFF451A03),
                                ),
                              ),
                              Text(
                                dateStr,
                                style: TextStyle(
                                  fontSize: 13,
                                  color: isSelected
                                      ? Colors.white.withOpacity(0.9)
                                      : const Color(0xFF92400E),
                                ),
                              ),
                            ],
                          ),
                        ),
                        Container(
                          padding: const EdgeInsets.symmetric(
                            horizontal: 10,
                            vertical: 4,
                          ),
                          decoration: BoxDecoration(
                            color: isSelected
                                ? Colors.white.withOpacity(0.2)
                                : const Color(0xFFFEF3C7),
                            borderRadius: BorderRadius.circular(8),
                          ),
                          child: Text(
                            'Available',
                            style: TextStyle(
                              fontSize: 11,
                              fontWeight: FontWeight.bold,
                              color: isSelected
                                  ? Colors.white
                                  : const Color(0xFFB05E27),
                            ),
                          ),
                        ),
                      ],
                    ),
                  ),
                );
              },
            ),

          // Actions
          Padding(
            padding: const EdgeInsets.all(20),
            child: Column(
              children: [
                SizedBox(
                  width: double.infinity,
                  height: 50,
                  child: ElevatedButton(
                    onPressed: selectedAlternate != null
                        ? () => widget.onDateSelected(selectedAlternate)
                        : null,
                    style: ElevatedButton.styleFrom(
                      backgroundColor: const Color(0xFFB05E27),
                      disabledBackgroundColor: const Color(0xFFD4A574),
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(12),
                      ),
                    ),
                    child: Text(
                      selectedAlternate != null
                          ? 'Select ${DateFormat('MMM d').format(selectedAlternate!)}'
                          : 'Select a Date',
                      style: const TextStyle(
                        fontSize: 15,
                        fontWeight: FontWeight.bold,
                        color: Colors.white,
                      ),
                    ),
                  ),
                ),
                const SizedBox(height: 10),
                TextButton(
                  onPressed: () => widget.onDateSelected(null),
                  child: const Text(
                    'Keep Original Date Anyway',
                    style: TextStyle(
                      fontSize: 14,
                      color: Color(0xFF92400E),
                      decoration: TextDecoration.underline,
                    ),
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
