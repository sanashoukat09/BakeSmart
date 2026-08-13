import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:table_calendar/table_calendar.dart';
import 'package:intl/intl.dart';
import '../../providers/order_provider.dart';
import '../../providers/auth_provider.dart';
import '../../models/order_model.dart';
import '../../core/constants/app_constants.dart';
import 'order_details_screen.dart';

class BakerDeliveryCalendarScreen extends ConsumerStatefulWidget {
  const BakerDeliveryCalendarScreen({super.key});

  @override
  ConsumerState<BakerDeliveryCalendarScreen> createState() =>
      _BakerDeliveryCalendarScreenState();
}

class _BakerDeliveryCalendarScreenState
    extends ConsumerState<BakerDeliveryCalendarScreen> {
  CalendarFormat _calendarFormat = CalendarFormat.month;
  DateTime _focusedDay = DateTime.now();
  DateTime? _selectedDay;

  @override
  Widget build(BuildContext context) {
    final user = ref.watch(currentUserProvider).valueOrNull;
    final ordersAsync = ref.watch(bakerOrdersProvider);

    return Scaffold(
      backgroundColor: const Color(0xFF1C1410),
      appBar: AppBar(
        backgroundColor: const Color(0xFF1C1410),
        elevation: 0,
        iconTheme: const IconThemeData(color: Color(0xFFF59E0B)),
        title: const Text(
          'Delivery Schedule',
          style: TextStyle(
            color: Color(0xFFF59E0B),
            fontWeight: FontWeight.w800,
            fontSize: 18,
          ),
        ),
      ),
      body: ordersAsync.when(
        data: (orders) {
          // Group orders by delivery date
          final Map<DateTime, List<OrderModel>> ordersByDate = {};
          for (var order in orders) {
            if (order.status == AppConstants.orderRejected ||
                order.status == AppConstants.orderCancelled) {
              continue; // Skip cancelled orders
            }
            final dateKey = DateTime(
              order.deliveryDate.year,
              order.deliveryDate.month,
              order.deliveryDate.day,
            );
            ordersByDate.putIfAbsent(dateKey, () => []);
            ordersByDate[dateKey]!.add(order);
          }

          return Column(
            children: [
              // Calendar
              Container(
                margin: const EdgeInsets.all(16),
                decoration: BoxDecoration(
                  color: const Color(0xFF2D1F17),
                  borderRadius: BorderRadius.circular(20),
                  border: Border.all(color: const Color(0xFF3E2A1F), width: 1.5),
                ),
                child: TableCalendar(
                  firstDay: DateTime.utc(2020, 1, 1),
                  lastDay: DateTime.utc(2030, 12, 31),
                  focusedDay: _focusedDay,
                  calendarFormat: _calendarFormat,
                  selectedDayPredicate: (day) => isSameDay(_selectedDay, day),
                  onDaySelected: (selectedDay, focusedDay) {
                    setState(() {
                      _selectedDay = selectedDay;
                      _focusedDay = focusedDay;
                    });
                  },
                  onFormatChanged: (format) {
                    setState(() {
                      _calendarFormat = format;
                    });
                  },
                  onPageChanged: (focusedDay) {
                    _focusedDay = focusedDay;
                  },
                  calendarStyle: CalendarStyle(
                    defaultTextStyle: const TextStyle(color: Color(0xFFD4A574)),
                    weekendTextStyle: const TextStyle(color: Color(0xFFF59E0B)),
                    todayDecoration: BoxDecoration(
                      color: const Color(0xFFF59E0B).withOpacity(0.3),
                      shape: BoxShape.circle,
                    ),
                    selectedDecoration: const BoxDecoration(
                      color: Color(0xFFF59E0B),
                      shape: BoxShape.circle,
                    ),
                    markerDecoration: const BoxDecoration(
                      color: Color(0xFF10B981),
                      shape: BoxShape.circle,
                    ),
                  ),
                  headerStyle: const HeaderStyle(
                    titleTextStyle: TextStyle(
                      color: Color(0xFFF59E0B),
                      fontSize: 16,
                      fontWeight: FontWeight.bold,
                    ),
                    formatButtonTextStyle: TextStyle(color: Color(0xFFD4A574)),
                    leftChevronIcon: Icon(Icons.chevron_left, color: Color(0xFFF59E0B)),
                    rightChevronIcon: Icon(Icons.chevron_right, color: Color(0xFFF59E0B)),
                    formatButtonVisible: false,
                  ),
                  daysOfWeekStyle: const DaysOfWeekStyle(
                    weekdayStyle: TextStyle(color: Color(0xFFD4A574)),
                    weekendStyle: TextStyle(color: Color(0xFFF59E0B)),
                  ),
                  calendarBuilders: CalendarBuilders(
                    markerBuilder: (context, date, events) {
                      final dateKey = DateTime(date.year, date.month, date.day);
                      final dayOrders = ordersByDate[dateKey] ?? [];
                      if (dayOrders.isEmpty) return null;

                      final capacity = user?.dailyOrderCapacity ?? 10;
                      final count = dayOrders.length;

                      Color indicatorColor;
                      if (count >= capacity) {
                        indicatorColor = const Color(0xFFDC2626); // Red
                      } else if (count >= capacity * 0.7) {
                        indicatorColor = const Color(0xFFF59E0B); // Yellow
                      } else {
                        indicatorColor = const Color(0xFF10B981); // Green
                      }

                      return Positioned(
                        bottom: 4,
                        child: Container(
                          padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 2),
                          decoration: BoxDecoration(
                            color: indicatorColor,
                            borderRadius: BorderRadius.circular(8),
                          ),
                          child: Text(
                            count.toString(),
                            style: const TextStyle(
                              color: Colors.white,
                              fontSize: 10,
                              fontWeight: FontWeight.bold,
                            ),
                          ),
                        ),
                      );
                    },
                  ),
                ),
              ),

              // Legend
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 20),
                child: Row(
                  mainAxisAlignment: MainAxisAlignment.spaceEvenly,
                  children: [
                    _buildLegendItem('Light', const Color(0xFF10B981)),
                    _buildLegendItem('Moderate', const Color(0xFFF59E0B)),
                    _buildLegendItem('At Capacity', const Color(0xFFDC2626)),
                  ],
                ),
              ),

              const SizedBox(height: 16),

              // Orders for selected day
              if (_selectedDay != null) ...[
                const Divider(color: Color(0xFF3E2A1F)),
                Expanded(
                  child: _buildOrdersList(
                    ordersByDate[DateTime(
                      _selectedDay!.year,
                      _selectedDay!.month,
                      _selectedDay!.day,
                    )] ?? [],
                  ),
                ),
              ] else
                const Expanded(
                  child: Center(
                    child: Text(
                      'Select a date to view orders',
                      style: TextStyle(
                        color: Color(0xFFD4A574),
                        fontSize: 14,
                      ),
                    ),
                  ),
                ),
            ],
          );
        },
        loading: () => const Center(
          child: CircularProgressIndicator(color: Color(0xFFF59E0B)),
        ),
        error: (error, stack) => Center(
          child: Text(
            'Error: $error',
            style: const TextStyle(color: Colors.red),
          ),
        ),
      ),
    );
  }

  Widget _buildLegendItem(String label, Color color) {
    return Row(
      children: [
        Container(
          width: 12,
          height: 12,
          decoration: BoxDecoration(
            color: color,
            shape: BoxShape.circle,
          ),
        ),
        const SizedBox(width: 4),
        Text(
          label,
          style: const TextStyle(
            color: Color(0xFFD4A574),
            fontSize: 12,
          ),
        ),
      ],
    );
  }

  Widget _buildOrdersList(List<OrderModel> orders) {
    if (orders.isEmpty) {
      return const Center(
        child: Text(
          'No orders for this date',
          style: TextStyle(
            color: Color(0xFFD4A574),
            fontSize: 14,
          ),
        ),
      );
    }

    return ListView.builder(
      padding: const EdgeInsets.all(16),
      itemCount: orders.length,
      itemBuilder: (context, index) {
        final order = orders[index];
        return Container(
          margin: const EdgeInsets.only(bottom: 12),
          decoration: BoxDecoration(
            color: const Color(0xFF2D1F17),
            borderRadius: BorderRadius.circular(16),
            border: Border.all(color: const Color(0xFF3E2A1F), width: 1.5),
          ),
          child: ListTile(
            contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
            leading: CircleAvatar(
              backgroundColor: const Color(0xFFF59E0B),
              child: Text(
                order.items.length.toString(),
                style: const TextStyle(
                  color: Color(0xFF1C1410),
                  fontWeight: FontWeight.bold,
                ),
              ),
            ),
            title: Text(
              order.customerName,
              style: const TextStyle(
                color: Color(0xFFF59E0B),
                fontWeight: FontWeight.bold,
              ),
            ),
            subtitle: Text(
              'Rs. ${order.totalAmount.toStringAsFixed(0)} • ${DateFormat('h:mm a').format(order.deliveryDate)}',
              style: const TextStyle(color: Color(0xFFD4A574), fontSize: 12),
            ),
            trailing: Container(
              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
              decoration: BoxDecoration(
                color: _getStatusColor(order.status).withOpacity(0.2),
                borderRadius: BorderRadius.circular(8),
              ),
              child: Text(
                order.status.toUpperCase(),
                style: TextStyle(
                  color: _getStatusColor(order.status),
                  fontSize: 10,
                  fontWeight: FontWeight.bold,
                ),
              ),
            ),
            onTap: () {
              Navigator.push(
                context,
                MaterialPageRoute(
                  builder: (context) => OrderDetailsScreen(orderId: order.id),
                ),
              );
            },
          ),
        );
      },
    );
  }

  Color _getStatusColor(String status) {
    switch (status) {
      case AppConstants.orderPlaced:
        return const Color(0xFF3B82F6);
      case AppConstants.orderAccepted:
      case AppConstants.orderPreparing:
        return const Color(0xFFF59E0B);
      case AppConstants.orderReady:
        return const Color(0xFF10B981);
      case AppConstants.orderDelivered:
        return const Color(0xFF8B5CF6);
      default:
        return const Color(0xFF6B7280);
    }
  }
}
